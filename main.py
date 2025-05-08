import discord
from discord import app_commands
from discord.ext import commands, tasks
import discord.types
from dotenv import load_dotenv
import os
import random as rd
import datetime
import gemini_summarization 
from collections import defaultdict
import sqlite3
from DBcontrol import fetch_bot_config, save_guild_all_channel_ids, save_guild_receive_channel, save_guild_filtered_channels,save_minutes,fetch_minutes
import glob
import re
#----------------- 환경변수 설정 ------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
#----------------- 봇 객체 기본 설정 ------------------

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
intents.members = True
SUM_Bot = commands.Bot(command_prefix='!', intents=intents)


# ----------------- 전역변수 ------------------

conn = sqlite3.connect("CHAT_DB.db")

All_CHANNEL_ID = defaultdict(list)
Recieve_channels ={}
filtered_channels= defaultdict(list)
message_buffer = defaultdict(lambda: defaultdict(list))



# ----------------- 공통 함수 ------------------

# 모든 채널 내용 긁기
async def fetch_all_chat_history(guild: discord.Guild):
    standard_time= datetime.datetime.now()- datetime.timedelta(days=1)
    standard_time.strftime('%Y-%m-%d %H:%M')
    # 일반 메세지
    messages = []
    thread_messages=[]
    for channel in guild.text_channels:
        if channel.id not in filtered_channels[guild.id]:
            async for msg in channel.history(after= standard_time):  
                if not msg.author.bot:  # 봇 메시지는 제외
                    messages.append(f"[{msg.author.display_name}] : {msg.content} \n[{msg.channel} 채널] [{(msg.created_at + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')}]\n")
        else:
            pass
    # 스레드 메세지
    for thread in guild.threads:
        thread_messages.append(f"** 스레드명 : {thread.name} ** \n")
        thread_channel=thread.parent
        if thread_channel.id not in filtered_channels[guild.id]:
            try:
                async for msg in thread.history(limit=100, after=standard_time):
                    thread_messages.append(f"[{msg.author.display_name}] : {msg.content} \n[{(msg.created_at + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')}]\n")
                thread_messages.append(f"\n")
            except:
                continue
    if messages or thread_messages:
        transcript = "\n".join(messages)  # 오래된 메시지부터 순서대로
        transcript2= "\n".join(thread_messages)
        # await interaction.followup.send(f"```🎙️ 텍스트 대화 목록입니다. 🎙️ \n\n\n {transcript[:1900]}```")
        # await interaction.followup.send(f"```🎙️ 스레드 대화 목록입니다. 🎙️ \n\n\n {transcript2[:1900]}```")   # 메시지 길이 제한 주의
    else:
        transcript = "📭 불러올 메시지가 없어요."
        transcript2= "📭 불러올 메시지가 없어요."
    return transcript, transcript2



# ----------------- 봇 이벤트 발생시 실행 ------------------

## 봇이 접속했을때(봇 서버가 열릴때)
@SUM_Bot.event
async def on_ready():
    print(f'봇이 로그인되었어요! 저는 {SUM_Bot.user}입니다.')
    global All_CHANNEL_ID, Recieve_channels, filtered_channels

    # DB에서 데이터를 불러와 전역 변수 초기화
    for guild in SUM_Bot.guilds:
        config = fetch_bot_config(guild.id)
        if config:
            All_CHANNEL_ID[guild.id] = config["all_channel_ids"]
            Recieve_channels[guild.id] = config["receive_channel"]
            filtered_channels[guild.id] = config["filtered_channels"]

    # 최신 채널 리스트 동기화 및 DB에 저장
    for guild in SUM_Bot.guilds:
        channel_names, channel_ids, categories = zip(*[
            (channel.name, channel.id, str(channel.type)) for channel in guild.channels]
        )
        buffer_channel_list = {
            f"{channel_name}, {category}": channel_id
            for channel_id, channel_name, category in zip(channel_ids, channel_names, categories)
            if "None" not in category
        }

        if All_CHANNEL_ID[guild.id] != buffer_channel_list:
            All_CHANNEL_ID[guild.id] = buffer_channel_list
            save_guild_all_channel_ids(guild.id, buffer_channel_list)
    
    scheduled_Scrapper.start()
    Send_minutes.start()
    reminder.start()
    
    try:
        synced = await SUM_Bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"❌ Sync failed: {e}")


## 새로운 서버에 참여했을 때
@SUM_Bot.event
async def on_guild_join(guild):
    print(f"✅ Joined new guild: {guild.name} (ID: {guild.id})")

    # 봇이 메시지를 보내거나 읽을 수 있는 채널 목록 저장 및 기본값 설정을 DB에 저장
    first_channel_id=0
    channel_names, channel_ids, categories = zip(*[
    (channel.name, channel.id, str(channel.type)) for channel in guild.channels]
    )
    global All_CHANNEL_ID
    All_CHANNEL_ID[guild.id] = {
        f"{channel_name}, {category}": channel_id
        for channel_id, channel_name, category in zip(channel_ids, channel_names, categories)
        if "None" not in category
    }
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            first_channel_id = int(channel.id)
            break
        else:
            pass

    save_guild_all_channel_ids(guild.id, All_CHANNEL_ID[guild.id])
    save_guild_receive_channel(guild.id, first_channel_id)
    print(f"활성화 된 채널 : {All_CHANNEL_ID[guild.id]}")


# @SUM_Bot.event
# async def on_guild_channel_update(before, after):
#     # 채널 이름 변경 등 감지
#     update_channel_in_db(after)

# @SUM_Bot.event
# async def on_guild_channel_create(channel):
#     add_channel_to_db(channel)

# @SUM_Bot.event
# async def on_guild_channel_delete(channel):

#----------------------------------- 봇 UI 클래스: 수신 채널 선택 -----------------------------------------------------

class Recieve_channel_select(discord.ui.Select):
    def __init__(self, interaction: discord.Interaction):
        options = [discord.SelectOption(label=x, description=f"{x} 채널에서 회의록을 송출합니다.") for x in  All_CHANNEL_ID[interaction.guild.id].keys()]
        super().__init__(placeholder="회의록 수신 채널 선택", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        Recieve_channels[interaction.guild.id] = All_CHANNEL_ID[interaction.guild.id][self.values[0]]
        save_guild_receive_channel(interaction.guild.id, Recieve_channels[interaction.guild.id])
        await interaction.response.send_message(
            f"✅ 선택한 채널: **{self.values[0]}**", ephemeral=True
        )

class RecieverView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.add_item(Recieve_channel_select(interaction))

#---------------------------------- 봇 UI 클래스: 채널 필터링 ----------------------------------------------------------

class channel_filter(discord.ui.Select):
    def __init__(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        # 현재 서버의 채널 리스트를 가져와 옵션으로 추가
        options = [
            discord.SelectOption(
                label=channel_name,
                description=f"{channel_name} 회의록을 만들 때, 해당 채널의 대화는 수집하지 않아요!"
            )
            for channel_name in All_CHANNEL_ID[guild_id].keys()
        ]
        super().__init__(placeholder="수집 x 채널 선택", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        # 선택된 채널을 필터 리스트에 추가
        channel_id = All_CHANNEL_ID[guild_id][self.values[0]]
        if channel_id not in filtered_channels[guild_id]:
            filtered_channels[guild_id].append(channel_id)
            save_guild_filtered_channels(guild_id, filtered_channels[guild_id])  # DB 업데이트
            await interaction.response.send_message(
                f"✅ 이제부터 **{self.values[0]}** 에서의 대화는 수집되지 않아요!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ **{self.values[0]}** 채널은 이미 필터링되어 있습니다.", ephemeral=True
            )

class FilterView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.add_item(channel_filter(interaction))

#---------------------------------- 봇 UI 클래스: 필터 해제 ----------------------------------------------------------

class channel_filter_remove(discord.ui.Select):
    def __init__(self, interaction: discord.Interaction):
        # 현재 필터 리스트를 가져옴
        guild_id = interaction.guild.id
        if guild_id in filtered_channels and filtered_channels[guild_id]:
            options = [
                discord.SelectOption(
                    label=f"채널 ID: {[k for k, v in All_CHANNEL_ID[guild_id].items() if v == channel_id][0]}: {channel_id}",
                    description="이 채널의 필터를 해제합니다."
                )
                for channel_id in filtered_channels[guild_id]
            ]
        else:
            options = [
                discord.SelectOption(
                    label="선택된 필터가 없습니다.",
                    description="필터가 설정되지 않았습니다.",
                    default=True
                )
            ]
        super().__init__(placeholder="필터 해제할 채널을 선택하세요.", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in filtered_channels and filtered_channels[guild_id]:
            # 선택된 필터를 제거
            channel_id_to_remove = int(self.values[0].split(": ")[2])
            channel_name_to_remove = self.values[0].split(": ")[1]
            filtered_channels[guild_id].remove(channel_id_to_remove)
            save_guild_filtered_channels(guild_id, filtered_channels[guild_id])  # DB 업데이트
            await interaction.response.send_message(
                f"✅ 채널 ID: **{channel_name_to_remove}** 의 필터가 해제되었습니다.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ 필터가 설정되지 않았습니다.", ephemeral=True
            )

class FilterRemoveView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.add_item(channel_filter_remove(interaction))


#----------------- 봇 키워드 정의 ------------------

@SUM_Bot.tree.command(name="설정_채널_수신_선택", description="🤖회정이가 어디로 회의록을 보내드리면 될지 알려주세요! (default: 첫번째 텍스트 채널)")
async def select_recieve_channel(interaction: discord.Interaction ):
    await interaction.response.send_message(f"수신 채널을 골라주세요! default는 첫번째 채널입니다!",view=RecieverView(interaction),ephemeral=True)

@SUM_Bot.tree.command(name="설정_채널_필터", description="🤖회정이가 회의록을 만들 때, 수집하면 안되는 채널을 선택해주세요! (default: 모든 채널 수집!)")
async def select_filter_channel(interaction: discord.Interaction ):
    await interaction.response.send_message(f"수집하면 안되는 채널을 알려주세요! 없다면 모든 채널을 수집합니다!",view=FilterView(interaction),ephemeral=True)

@SUM_Bot.tree.command(name="설정_채널_필터_해제", description="🤖회정이가 필터링된 채널을 다시 활성화합니다!")
async def remove_filter_channel(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in filtered_channels and filtered_channels[guild_id]:
        await interaction.response.send_message(
            "필터를 해제할 채널을 선택하세요!", view=FilterRemoveView(interaction), ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ 현재 필터링된 채널이 없습니다.", ephemeral=True
        )

@SUM_Bot.tree.command(name="주사위_굴리기", description="주사위를 굴려서 오늘의 운을 확인해볼까요? 🎲 뭐, 할 때마다 달라지긴 하지만요. 😀🤣")
async def ping(interaction: discord.Interaction):
    num = rd.randint(1,66)
    if num%2==0 and num>50:
        await interaction.response.send_message(f"{interaction.user.display_name}님의 💖 주사위 결과 🌟🌟🎲🌟🌟{num}이 나왔습니다. 주사위에서 범상치 않은 기운이 느껴집니다. 😁😁")
    elif num%2!=0 and num>50:
        await interaction.response.send_message(f"🎉🎉🎉 오오오오~ {interaction.user.display_name}님의 주사위 결과 🎲{num}이 나왔습니다. 좋은 하루가 될 것 같은 느낌? 🎊🎉🎉")
    elif num%2==0 and num<=50 and num>30:
        await interaction.response.send_message(f"흠... {interaction.user.display_name}님의 주사위 결과 🎲{num}이 나왔습니다. 꽤 괜찮은 조합이군요! 🤔🤔")
    elif num%2!=0 and num<=50 and num>30:
        await interaction.response.send_message(f"오... {interaction.user.display_name}님의 주사위 결과 🎲{num}이 나왔습니다. 오늘 커피 한 잔 때리기 좋은 날씨군요. ☕ ")
    elif num%2==0 and num<=30 and num>=10:
        await interaction.response.send_message(f"{interaction.user.display_name}님의 주사위 결과 🎲{num}이 나왔습니다. 조금 심심한 숫자군요... 다시 한 번 굴려보실래요? 🎲🎲🎲🎲😁 ")
    elif num%2!=0 and num<=30 and num>=10:
        await interaction.response.send_message(f"..... {interaction.user.display_name}님의 주사위 결과 🎲{num}이 나왔습니다. ......어디까지나 랜덤이니까요.🎰 ")
    else: 
        await interaction.response.send_message(f"{interaction.user.display_name}님의 주사위를 힘차게 굴려보았지만 🎲{num}이 나왔습니다. 너무 힘을 줬던 걸까요?💪")

@SUM_Bot.tree.command(name="챗봇_대화하기", description="당신의 친절한 친구 회정이에요. 언제든지 편하게 물어봐요. 😊❤️")
@app_commands.describe(prompt="당신의 개발에 도움을 줄 수 있을지도...?")
async def chat_with_bot(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    result = gemini_summarization.chat_with_bot(input=prompt, session_id= str(interaction.user), guild_id = interaction.guild.id )
    await interaction.followup.send(result)

@SUM_Bot.tree.command(name="설정_명령어_리스트", description="등록된 명령어들이 뭐가있는지 살펴보아요!")
async def show_commands(interaction: discord.Interaction):
    cmds = SUM_Bot.tree.get_commands()
    command_names = [cmd.name for cmd in cmds]
    print(interaction.guild.id, type(interaction.guild.id))
    await interaction.response.send_message(f"등록된 명령어: {', '.join(command_names)}")

@SUM_Bot.tree.command(name="대화내역_모든_채널", description="모든 채널에서 있었던 대화 내역을 출력해줘요! 한 번에 보기 좋겠죠?!")
async def fetch_all_messages(interaction: discord.Interaction):
    await interaction.response.defer()  # 응답 지연 처리 (타임아웃 방지)
    result= await fetch_all_chat_history(interaction.guild)
    transcript,transcript2=result[0],result[1]
    await interaction.followup.send(f"```🎙️ 텍스트 대화 목록입니다. 🎙️ \n\n\n {transcript[:1900]}```")
    await interaction.followup.send(f"```🎙️ 스레드 대화 목록입니다. 🎙️ \n\n\n {transcript2[:1900]}```")   # 메시지 길이 제한 주의


@SUM_Bot.tree.command(name="대화내역_현재_채널", description="해당 채널의 최근 대화 내역을 출력해줘요! 한번에 보기 좋겠죠?")
async def fetch_messages(interaction: discord.Interaction):
    await interaction.response.defer()  # 응답 지연 처리 (타임아웃 방지)
    standard_time= datetime.datetime.now()- datetime.timedelta(days=1)
    standard_time.strftime('%Y-%m-%d %H:%M')
    # 일반 메세지
    messages = []
    async for msg in interaction.channel.history(after= standard_time):  # 최근 50개 불러오기
        if not msg.author.bot:  # 봇 메시지는 제외
            messages.append(f"[{msg.author.display_name}] : {msg.content} \n[{(msg.created_at + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')}]\n")
   
    # 스레드 메세지
    thread_messages=[]
    for thread in interaction.channel.threads:
        thread_messages.append(f"** 스레드명 : {thread.name} ** \n")
        try:
            async for msg in thread.history(limit=100):
                thread_messages.append(f"[{msg.author.display_name}] : {msg.content} \n[{(msg.created_at + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')}]\n")
            thread_messages.append(f"\n")
        except:
            continue

    if messages or thread_messages :
        transcript = "\n".join(messages)  # 오래된 메시지부터 순서대로
        transcript2= "\n".join(thread_messages)
        await interaction.followup.send(f"```🎙️ 텍스트 대화 목록입니다. 🎙️ \n\n\n {transcript[:1900]}```")
        await interaction.followup.send(f"```🎙️ 스레드 대화 목록입니다. 🎙️ \n\n\n {transcript2[:1900]}```")  # 메시지 길이 제한 주의
    else:
        await interaction.followup.send("📭 불러올 메시지가 없어요.")

@SUM_Bot.tree.command(name="회의록_실시간_정리", description="정기 회의록의 내용을 지금 보고 싶다고요? 지금 당장 오늘의 회의록을 송출해줘요! 📋")
async def summarize_messages(interaction: discord.Interaction):
    await interaction.response.defer()
    now = datetime.datetime.now().strftime('%Y-%m-%d')
    try:
        answer=gemini_summarization.summarizer(interaction.guild.id)
        saving=save_minutes(interaction.guild.id, answer)
        file_name = f"minutes/{interaction.guild.id}_{now}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(answer)
        print(saving)
        await interaction.followup.send(answer)
    except Exception as e:
        await interaction.followup.send(f"에러 발생. 🚨 {e} 아직 충분한 대화가 모이지 않았어요!")


# ---------------------------------        음성 관련 부분 -----------------------------------------


@SUM_Bot.tree.command(name="음성채널_입장", description="회정이가, 현재 접속중인 음성채널에 참여해요! 🔊")
async def voice_join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"회정이가 성공적으로 음성채널에 입장했습니다. 여러분의 회의 내용이 녹음될 수 있습니다. 🔉 🎙️🎙️ 💖")
    else:
        await interaction.response.send_message(f"먼저 음성 채널에 입장한 후에 초대해주세요.")


@SUM_Bot.tree.command(name="음성채널_나가", description="회정이가, 현재 접속중인 음성채널에서 쫓겨나요! 🥹😭😭😭😢")
async def voice_quit(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("회의를 마무리하셨을까요? 수고하셨습니다! 아니라면, 다시 초대해주세요! 😄")
    else:
        await interaction.response.send_message("제가 음성 채널에 있는 것도 아닌데 어딜 나가라는 건가요....😭😭")


# @SUM_Bot.tree.command(name="Meeting description", description="오늘의 회의를 요약하고 싶으신가요? 지금 시간을 기준으로 하루의 내용을 요약해드릴게요! 📋")
# async def ping(interaction: discord.Interaction):
#     await interaction.response.defer()

#     await interaction.response.send_message("pong!")


#------------------------- 스케쥴링 태스크 파트 --------------------------------------


# 채팅 기반 회의록을 뿌려주는 시간 10시, 그러므로 9시 50분쯤에 이 함수를 실행해서 요약한 파일을 DB에 저장하게한다.
@tasks.loop(minutes=1)
async def scheduled_Scrapper():
    now = datetime.datetime.now().time()
    target_time = datetime.time(hour=10, minute=5)  # 오전 7시 10분
    if now.hour == target_time.hour and now.minute == target_time.minute:
        for guild in SUM_Bot.guilds:
            try:
                result = await fetch_all_chat_history(guild)
                transcript,transcript2=result[0],result[1]
                text = f"```***일반 대화 목록입니다. ***\n\n\n {transcript} \n\n\n***스레드 대화 목록입니다. ***\n\n\n {transcript2}```"
                file_name = f"chat_log/{guild.id}_chatlog.txt"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                print(f"에러발생 {e}")
                    # 또는 특정 커맨드 함수 직접 호출도 가능
                    # await your_command_callback(ctx_or_fake_context)

@tasks.loop(minutes=1)
async def Send_minutes():
    now = datetime.datetime.now().time()
    target_time = datetime.time(hour=10, minute=10)  # 오전 8시 30분
    if now.hour == target_time.hour and now.minute == target_time.minute:
        for guild in SUM_Bot.guilds:
            try:
                result = gemini_summarization.summarizer(guild.id)
                channel = SUM_Bot.get_channel(int(Recieve_channels[guild.id]))
                await channel.send(result)
                print(f"{channel.guild.name} 전송 완료")
                saving=save_minutes(guild.id, result)
                file_name = f"minutes/{guild.id}_{now.strftime('%Y-%m-%d')}.txt"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(result)
                print(saving)
            except Exception as e:
                print(f"에러발생 {e}")



# 매일 9시 10분에 할 일을 리마인드 시켜주는 기능
@tasks.loop(minutes=1)
async def reminder():
    now = datetime.datetime.now().time()
    target_time = datetime.time(hour=10, minute=20)  # 오전 9시 10분
    now_time=datetime.datetime.now().strftime('%Y-%m-%d')
    if now.hour == target_time.hour and now.minute == target_time.minute:
        for guild in SUM_Bot.guilds:
            users=guild.members
            user_dict = {user.display_name : user.id for user in users}
            print(user_dict)
            minutes = fetch_minutes(guild.id,now_time)
            #user_names = re.findall(r"\[ \] ([^:]+):", minutes)
            try:
                channel = SUM_Bot.get_channel(int(Recieve_channels[guild.id]))
                for user_name in users:
                    if user_name.bot:
                        continue
                    else:
                        remind = gemini_summarization.reminder(minutes, user_name.display_name)
                        await channel.send(f"""{user_name.mention} {now_time} 금일의 리마인더 입니다. \n{remind}""") 
                print(f"{guild.name} 전송 완료 {guild.members}")
            except Exception as e :
                print(f"{guild.name} 전송 실패 {e}")
                # for user_name in user_names:
                #     await channel.send(f"""회의록이 없거나, 할당된 일이 없습니다. 회의록을 다시 확인해주세요.""") 
                continue

        


#----------------- 봇 객체 생성 및 토큰 ------------------

SUM_Bot.run(TOKEN)

