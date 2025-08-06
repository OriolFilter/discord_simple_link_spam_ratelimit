import discord

from discord.ext import tasks
import os
from urlextract import URLExtract
from urllib.parse import urlparse
import asyncio
from MessagesClasses import *
from typing import Union


class ExceededTotalLinksRateLimit:
    pass


class ExceededSameLinkRateLimit:
    pass


class ModerationEmbed(discord.ui.View):
    # Maybe do a moderation embed message that also sets who updated/moderated the bot etc. # TODO
    # Maybe can make use of `original_response_message` for that
    # Maybe use an embed for more fancy info display? IDK
    allowed_moderation_roles: [int]
    moderated_discord_user: Union[discord.User, discord.Member]
    disabled = False

    def __init__(self, moderated_discord_user: Union[discord.User, discord.Member], allowed_moderation_roles: [int],
                 timeout=1200,  # 20 minutes
                 reason: ExceededTotalLinksRateLimit | ExceededSameLinkRateLimit = None):
        self.allowed_moderation_roles = allowed_moderation_roles
        self.moderated_discord_user = moderated_discord_user
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Remove timeout", style=discord.ButtonStyle.success)
    async def remove_timout(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.style = discord.ButtonStyle.green
        if interaction.user.guild_permissions.administrator or (
                self.is_user_moderator(interaction.user) or
                interaction.user.guild_permissions.moderate_members  # Refers to timeout
        ):
            try:
                await self.moderated_discord_user.timeout(datetime.timedelta(seconds=0),
                                                          reason=f"Removing timeout. Executed by user {interaction.user}")
                await interaction.message.reply(f"User {interaction.user.mention} removed the timeout for {self.moderated_discord_user.mention}")
            except discord.errors.Forbidden:
                await interaction.message.reply(f"I (bot) don't have enough permissions to **TIMEOUT** {self.moderated_discord_user.mention} (being able to timeout is required to un-timeout).")
            except Exception as e:
                await interaction.message.reply(f"Unexpected error\n```{e}```")

            button.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.message.reply(
                content=f"User {interaction.user.mention} doesn't have permissions to timeout users.")

    @discord.ui.button(label="Kick User", style=discord.ButtonStyle.gray)
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.style = discord.ButtonStyle.gray
        if interaction.user.guild_permissions.administrator or (
                self.is_user_moderator(interaction.user) or
                interaction.user.guild_permissions.kick_members
        ):
            try:
                await self.moderated_discord_user.kick(reason=f"Kicked user. Executed by user {interaction.user}")
                await interaction.message.reply(
                    f"User {interaction.user.mention} kicked {self.moderated_discord_user.mention}")
            except discord.errors.Forbidden:
                await interaction.message.reply(f"I (bot) don't have enough permissions to **KICK** {self.moderated_discord_user.mention}")
            except Exception as e:
                await interaction.message.reply(f"Unexpected error\n```{e}```")
        else:
            await interaction.message.reply(
                content=f"User {interaction.user.mention} doesn't have permissions to kick users.")

    @discord.ui.button(label="Ban and remove messages from the last hour", style=discord.ButtonStyle.danger)
    async def ban_user_and_cleanup_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        # button.style = discord.ButtonStyle.green

        if interaction.user.guild_permissions.administrator or (
                self.is_user_moderator(interaction.user) or
                interaction.user.guild_permissions.ban_members
        ):
            try:
                await self.moderated_discord_user.ban(reason=f"Baned user and deleted messages from the last hour "
                                                             f"(3600s). Executed by user {interaction.user}.",
                                                      delete_message_seconds=3600)
                await interaction.message.reply(
                    f"User {interaction.user.mention} baned {self.moderated_discord_user.mention} "
                    f"and deleted messages from the last hour (3600s).")
            except discord.errors.Forbidden:
                await interaction.message.reply(f"I (bot) don't have enough permissions to **BAN** {self.moderated_discord_user.mention}")
            except Exception as e:
                await interaction.message.reply(f"Unexpected error\n```{e}```")
        else:
            await interaction.message.reply(
                content=f"User {interaction.user.mention} doesn't have permissions to kick users.")

        button.disabled = True  # Should disable all the buttons.
        # await
        await interaction.message.edit(view=self)

    def is_user_moderator(self, user: discord.User | discord.Member) -> bool:
        ## Check roles
        if len(set([role.id for role in user.roles]) & set(self.allowed_moderation_roles)) > 0:
            print(f"Matched roles ID: {set([role.id for role in user.roles]) & set(self.allowed_moderation_roles)}")
            return True
        return False


@dataclasses.dataclass
class Config:
    messages_db: MessagesDB
    timeout_hours: int
    moderation_roles: list[int]
    server_id: str | None  # Int? TODO
    # thresholds_seconds: int
    # count_threshold: 5


class MyBot(discord.Client):
    messages_cleanup_lock = asyncio.Lock
    lock_timeout_cleanup = asyncio.Lock
    lock_healthcheck = asyncio.Lock
    __connected: bool = False

    def __init__(self, intents: discord.Intents = None):
        intents.message_content = True
        super().__init__(intents=intents)
        self._set_as_disconnected()

        self.config = Config(
            messages_db=MessagesDB(),
            timeout_hours=5,
            moderation_roles=[int(role_id) for role_id in os.getenv("DISCORD_MODERATION_ROLES", "").split()],
            server_id=os.getenv("DISCORD_SERVER_ID")
        )

        self.messages_cleanup_lock = asyncio.Lock()
        self.lock_timeout_cleanup = asyncio.Lock()
        self.lock_healthcheck = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self.__connected

    def _set_as_connected(self):
        self.__connected = True

    def _set_as_disconnected(self):
        self.__connected = False

    async def on_resumed(self):
        self._set_as_connected()
        print("Reconnected!")

    async def on_connect(self):
        self._set_as_connected()
        print("Connected!")

    async def on_disconnect(self):
        self._set_as_disconnected()
        print("Disconnected!")

    async def on_ready(self):
        print(f'We have logged in as {client.user}')
        self.messages_cleanup.start()
        self.task_timeout_cleanup.start()
        self.task_check_health.start()

    async def on_message(self, message: discord.Message):
        print(self.config.server_id)
        if message.guild.id != int(self.config.server_id):
            print(f"Wrong server {message.author}")
        elif message.author.bot:
            pass  # Ignore bots
        elif not message.guild.id:
            pass  # Ignore messages without guild id
        else:
            extractor = URLExtract()

            urlextract = extractor.find_urls(message.content)
            sanitized_urls = [f"{urlparse(link).netloc}/{urlparse(link).path}" for link in urlextract]
            # Ignore cases where no links are provided.
            if len(sanitized_urls) > 0:
                message_object = MessageRecord(
                    id=message.id,
                    author_id=message.author.id,
                    server_id=message.guild.id,
                    creation_timestamp=message.created_at,
                    urls=sanitized_urls,
                    message_url=message.jump_url
                )
                self.config.messages_db.add_message(message_object)

                await self.review_user(message)

    async def review_user(self, message: discord.Message):
        author_messages_db: MessagesDBServerAuthor = self.config.messages_db.servers.get(message.guild.id).authors.get(
            message.author.id)
        global global_same_link_threshold

        triggered_timeout: bool = False
        triggered_timeout_url: str | None = None

        # sanitized_urls = []
        sanitized_urls = author_messages_db.get_uniq_urls()
        # print(sanitized_urls)

        # Review user for same URL posted.
        i = 0
        while not triggered_timeout and i < len(sanitized_urls):
            url: str = sanitized_urls[i]
            count = self.config.messages_db.count_links_from_author(
                server_id=message.guild.id,
                author_id=message.author.id,
                timestamp=message.created_at,
                url=url
            )
            print(f"User '{message.author.id}' Count '{count}' for URL '{url}'")
            if count > global_same_link_threshold:
                triggered_timeout = True
                triggered_timeout_url = url
            i += 1
        del url, count

        # Review user total URL posted.
        if not triggered_timeout:
            count = self.config.messages_db.count_total_sent_links_from_author(
                server_id=message.guild.id,
                author_id=message.author.id,
                timestamp=message.created_at
            )
            print(f"User '{message.author.id}' Total count '{count}'")
            if count > global_total_links_threshold:
                triggered_timeout = True
                triggered_timeout_url = "Multiple URL"  # IDK TODO

        if triggered_timeout and not author_messages_db.timed_out:
            await message.channel.send("This message has buttons!",
                                       view=ModerationEmbed(moderated_discord_user=message.author,
                                                            allowed_moderation_roles=self.config.moderation_roles)
                                       )

            print(f"user {message.author.name} triggered timeout with the url {triggered_timeout_url}")

            # 0. Check if user is timed out (to avoid further triggers)
            # if not message.author.is_timed_out():
            # 1. Timeout the user
            failed_to_timeout = False
            author_messages_db.set_cache_timeout()
            await message.channel.send(f"# Preemtive timeout {message.author.mention}\n"
                                       f"## Timout hours: {self.config.timeout_hours}\n"
                                       f"If you believe this is was a mistake, please contact the "
                                       f"moderators/admins.\n")
            try:
                await message.author.timeout(datetime.timedelta(hours=self.config.timeout_hours),
                                             reason=f"Triggered rate limit ({global_same_link_threshold} instances) with URL {triggered_timeout_url}")
            except discord.errors.Forbidden:
                failed_to_timeout = True
                await message.channel.send("Missing permissions when timing out user")

            # 3 Mention in the moderation_channel
            moderation_channel = None
            if message.guild.public_updates_channel:
                moderation_channel = message.guild.public_updates_channel
            else:
                moderation_channel = message.channel

            mod_pings = ""
            if len(self.config.moderation_roles) < 1:
                server_owner = self.client.get_user(int(message.guild.owner_id))
                mod_pings = f"\n++ {server_owner}"

            else:
                mod_pings = "\n++ ".join([f"<@&{role_id}>" for role_id in self.config.moderation_roles])

            # Messages currently stored from the user
            possible_recent_messages_from_user: list[MessageRecord] = self.get_recent_messages_from_user(
                message.author.id)
            formated_list_possible_recent_messages_from_user = ""
            for possible_message in possible_recent_messages_from_user:
                possible_message: MessageRecord
                formated_list_possible_recent_messages_from_user += f"- {possible_message.message_url}\n"
            del possible_message

            if failed_to_timeout:
                # moderation_channel.send()
                await moderation_channel.send(
                    f"Wasn't able to timeout user {message.author.mention} due to an error of permissions.\nList of possible recent messages:\n{formated_list_possible_recent_messages_from_user}\n{mod_pings}")
            else:
                await moderation_channel.send(
                    f"User {message.author.mention} has been timeout for {self.config.timeout_hours} hours.\nList of possible recent messages:\n{formated_list_possible_recent_messages_from_user}\n{mod_pings}")
            # 3. Remove recent messages  # Embed in the admins channel for admins to decide what to do with it?

    def get_recent_messages_from_user(self, user_id: int) -> list[MessageRecord]:
        for server in self.config.messages_db.servers.values():
            server: MessagesDBServer
            for author in server.authors.values():
                author: MessagesDBServerAuthor
                if author.id == user_id:
                    return author.messages

    @tasks.loop(seconds=5)
    async def messages_cleanup(self):
        async with self.messages_cleanup_lock:
            print("Messages cleanup job start")
            global global_thresholds_seconds
            job_start_timestamp = datetime.datetime.now(datetime.UTC)
            bottom_threshold = job_start_timestamp - datetime.timedelta(
                seconds=global_thresholds_seconds + 5)  # Adding an extra margin just in case
            for server in self.config.messages_db.servers.values():
                server: MessagesDBServer
                for author in server.authors.values():
                    author: MessagesDBServerAuthor
                    for message in author.messages:
                        message: MessageRecord
                        if message.creation_timestamp < bottom_threshold:
                            print(
                                f"[CACHE CLEANUP] Deleting message {message.id} from user {message.author_id} (server {message.server_id})")
                            author.messages.remove(message)

    @tasks.loop(seconds=15)
    async def task_timeout_cleanup(self):
        async with self.lock_timeout_cleanup:
            print("Timeout cleanup job start")
            job_start_timestamp = datetime.datetime.now(datetime.UTC)
            bottom_threshold = job_start_timestamp - datetime.timedelta(
                seconds=global_thresholds_seconds + 5)  # Adding an extra margin just in case
            for server in self.config.messages_db.servers.values():
                server: MessagesDBServer
                for author in server.authors.values():
                    author: MessagesDBServerAuthor
                    if author.timed_out and author.timed_out_timestamp < bottom_threshold:
                        author.clear_cache_timout()

    @tasks.loop(seconds=5)
    async def task_check_health(self):
        file = '/tmp/healthy'
        print(f"Is connected? {self.is_connected}")

        if self.is_connected:
            with open(file, "w") as f:
                f.write(("NOK", "OK")[self.is_connected])
        else:
            try:
                os.remove(file)
            except OSError:
                pass

            try:
                await self.connect()
            except Exception as e:
                print(f"Error while attempting to reconnect. \n{e}")


global_thresholds_seconds = 5  # Every when to clean up the internal cache/or also named as how wide is the margin.
global_same_link_threshold = 3  # Total number of hits (per used) allowed. Triggers at 4
global_total_links_threshold = 10  # Allowing a total of 10 links sent per used within 5 seconds. Triggers at 11

if __name__ == '__main__':
    _intents = discord.Intents.default()
    _intents.message_content = True
    _intents.members = True

    token = os.getenv("DISCORD_API_TOKEN")
    client = MyBot(_intents)
    client.run(token)
