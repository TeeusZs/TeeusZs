import pprint
import asyncio
import traceback

import discord
from discord.ext import commands

from youtube_dl import YoutubeDL
import re

URL_REG = re.compile(r'https?://(?:www\.)?.+')
YOUTUBE_VIDEO_REG = re.compile(r"(https?://)?(www\.)?youtube\.(com|nl)/watch\?v=([-\w]+)")

class music(commands.Cog):
    def __init__(self, client):
        self.client = client

        #all the music related stuff
        self.is_playing = False
        self.event = asyncio.Event()

        # 2d array containing [song, channel]
        self.music_queue = []
        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            #'default_search': 'auto',
            'extract_flat': True
        }
        self.FFMPEG_OPTIONS = {'before_options': '-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.vc = ""

     #searching the item on youtube
    def search_yt(self, item):

        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                if (yt_url:=YOUTUBE_VIDEO_REG.match(item)):
                    item = yt_url.group()
                elif not URL_REG.match(item):
                    item = f"ytsearch:{item}"
                info = ydl.extract_info(item, download=False)
            except Exception:
                traceback.print_exc()
                return False

        try:
            entries = info["entries"]
        except KeyError:
            entries = [info]

        if info["extractor_key"] == "YoutubeSearch":

            entries = entries[:1]

        tracks = []

        for t in entries:

            tracks.append({'source': f'https://www.youtube.com/watch?v={t["id"]}', 'title': t['title']})

        #if search:
        #    tracks = {'source': info['formats'][0]['url'], 'title': info['title']}

        return tracks

    # infinite loop checking 
    async def play_music(self):

        self.event.clear()

        if len(self.music_queue) > 0:

            self.is_playing = True

            m_url = self.music_queue[0][0]['source']

            # If source was a stream (not downloaded), so we should regather to prevent stream expiration
            with YoutubeDL(self.YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(m_url, download=False)
                    m_url = info['formats'][0]['url']
                except Exception:
                    return False

            #try to connect to voice channel if you are not already connected

            if self.vc == "" or not self.vc.is_connected() or self.vc == None:
                self.vc = await self.music_queue[0][1].connect()
            else:
                await self.vc.move_to(self.music_queue[0][1])

            #remove the first element as you are currently playing it
            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda l: self.client.loop.call_soon_threadsafe(self.event.set))
            await self.event.wait()
            await self.play_music()
        else:
            self.is_playing = False
            self.music_queue.clear()
            
    @commands.command(name="help",alisases=['ajuda'],help="help command")
    async def help(self,ctx):
        helptxt = ''
        for command in self.client.commands:
            helptxt += f'**{command}** - {command.help}\n'
        embedhelp = discord.Embed(
            colour = 7485893,#white
            title=f'Comandos do {self.client.user.name}',
            description = helptxt+'\n[]()'
        )
        embedhelp.set_thumbnail(url=self.client.user.avatar_url)
        await ctx.send(embed=embedhelp)


    @commands.command(name="play", help="Play a song from YouTube",aliases=['p','tocar'])
    async def p(self, ctx: commands.Context, *, query:str = "dk morreu - osteve"):
        
        try:
            voice_channel = ctx.author.voice.channel
        except:
        #if voice_channel is None:
            #you need to be connected so that the bot knows where to go
            embedvc = discord.Embed(
                colour= 7485893,#white
                description = 'To play a song, first connect to a voice channel.'
            )
            await ctx.send(embed=embedvc)
            return
        else:
            songs = self.search_yt(query)
            if type(songs) == type(True):
                embedvc = discord.Embed(
                    colour= 7485893,#white
                    description = 'Something went wrong! Try changing or configuring the playlist/video or writing its name again!'
                )
                await ctx.send(embed=embedvc)
            else:

                if (size:=len(songs)) > 1:
                    txt = f"You added **{size} songs** in queue!"
                else:
                    txt = f"you added the song **{songs[0]['title']}** the queue!"

                embedvc = discord.Embed(
                    colour= 7485893,#white
                    description = f"{txt}\n\n[**If you want to help click here**.](https://www.youtube.com/watch?v=vA3rzGF3rLo&t=2s)"
                )
                await ctx.send(embed=embedvc)
                for song in songs:
                    self.music_queue.append([song, voice_channel])

                if self.is_playing == False:
                    await self.play_music()

    @commands.command(name="**queue**", help="Shows the current songs in the queue.",aliases=['q','fila'])
    async def q(self, ctx):
        retval = ""
        for i in range(0, len(self.music_queue)):
            retval += f'**{i+1} - **' + self.music_queue[i][0]['title'] + "\n"

        print(retval)
        if retval != "":
            embedvc = discord.Embed(
                colour= 7485893,#white
                description = f"{retval}"
            )
            await ctx.send(embed=embedvc)
        else:
            embedvc = discord.Embed(
                colour= 7485893,
                description = 'There are no songs in the queue at the moment..'
            )
            await ctx.send(embed=embedvc)

    @commands.command(name="skip", help="Skip the current song currently playing.",aliases=['pular',"s"])
    @commands.has_permissions(manage_channels=True)
    async def skip(self, ctx):
        if self.vc != "" and self.vc:
            self.vc.stop()
            embedvc = discord.Embed(
                colour= 7485893,#white
                description = f"Você pulou a música."
            )
            await ctx.send(embed=embedvc)

    @skip.error #Erros para kick
    async def skip_error(self,ctx,error):
        if isinstance(error, commands.MissingPermissions):
            embedvc = discord.Embed(
                colour= 7485893,
                description = f"You need **Manage Channels** permission to skip songs."
            )
            await ctx.send(embed=embedvc)     
        else:
            raise error

    @commands.command(aliases=["parar", "sair", "leave", "l"])
    async def stop(self, ctx: commands.Context):

        embedvc = discord.Embed(colour= 7485893)

        if not ctx.me.voice:
            embedvc.description = "I'm not connected to a voice channel."
            await ctx.reply(embed=embedvc)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.me.voice.channel:
            embedvc.description = "You need to be on my current voice channel to use this command."
            await ctx.reply(embed=embedvc)
            return

        if any(m for m in ctx.me.voice.channel.members if not m.bot and m.guild_permissions.manage_channels) and not ctx.author.guild_permissions.manage_channels:
            embedvc.description = "You are currently not allowed to use this command."
            await ctx.reply(embed=embedvc)
            return

        self.is_playing = False
        self.music_queue.clear()
        await self.vc.disconnect(force=True)

        embedvc.colour = 7485893
        embedvc.description = "you stopped the player"
        await ctx.reply(embed=embedvc)

def setup(client):
    client.add_cog(music(client))