from dataclasses import field

import discord

from typing import Union, Type
from MessagesClasses import *
from ConfigClasses import *
from main import MyBot


@dataclasses.dataclass
class ExceededTotalLinksRateLimit:
    pass


@dataclasses.dataclass
class ExceededSameLinkRateLimit:
    urls: [str]


@dataclasses.dataclass
class ModerationEmbed:
    pass


@dataclasses.dataclass
class ModerationStatus:
    """Class used to keep track of the moderation status/actions before creating the widged/button object.
    Used to craft the messages to send."""
    preemptive_timeout_applied: bool = False
    user_kicked: bool = False  # Unused
    user_banned: bool = False  # Unused

    trigger_reason: ExceededSameLinkRateLimit | ExceededTotalLinksRateLimit | None = field(default=None)
    # possible_recent_messages: [MessageRecord] = field(efault_factory=list)
    #
    # # roles_to_mention = [int] # Redundant, use self.config.moderation_roles
    users_to_mention: [discord.User] = field(default_factory=list)


class ModerationEmbedClass(discord.ui.View):
    allowed_moderation_roles: [int]
    moderated_discord_user: Union[discord.User, discord.Member]
    disabled = False
    config: Config
    moderation_status: ModerationStatus
    recent_messages_storage: [MessageRecord] = []
    # When updating the message, either update contents as text, or use an Embed. If it's set to no, it will assume it
    # doesn't have permissions to send embeds and will complain about it!
    embed_mode = True

    user_that_kicked: Union[discord.User, discord.Member] = None
    user_that_banned: Union[discord.User, discord.Member] = None
    user_that_removed_timeout: Union[discord.User, discord.Member] = None

    def __init__(self, moderated_discord_user: Union[discord.User, discord.Member], allowed_moderation_roles: [int],
                 config: Config,
                 moderation_status: ModerationStatus,
                 discord_bot: MyBot,
                 timeout=1200,  # 20 minutes
                 ):
        self.allowed_moderation_roles = allowed_moderation_roles
        self.moderated_discord_user = moderated_discord_user
        self.config = config
        self.moderation_status = moderation_status
        self.discord_bot = discord_bot
        super().__init__(timeout=timeout)

    # TODO
    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     return False

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
                await interaction.message.reply(
                    f"User {interaction.user.mention} removed the timeout for {self.moderated_discord_user.mention}")

                self.user_that_removed_timeout = interaction.user
                button.disabled = True
                # TODO check for defer/fix
                # await interaction.response.defer()
                await interaction.message.edit(view=self, embed=self.get_status_embed())

            except discord.errors.Forbidden:
                await interaction.message.reply(
                    f"I (bot) don't have enough permissions to **TIMEOUT** {self.moderated_discord_user.mention} (being able to timeout is required to un-timeout).")
            except Exception as e:
                await interaction.message.reply(f"Unexpected error\n```{e}```")

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

                self.user_that_kicked = interaction.user
                button.disabled = True
                await interaction.message.edit(view=self, embed=self.get_status_embed())

            except discord.errors.Forbidden:
                await interaction.message.reply(
                    f"I (bot) don't have enough permissions to **KICK** {self.moderated_discord_user.mention}")

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

                self.user_that_banned = interaction.user
                button.disabled = True
                await interaction.message.edit(view=self, embed=self.get_status_embed())

            except discord.errors.Forbidden:
                await interaction.message.reply(
                    f"I (bot) don't have enough permissions to **BAN** {self.moderated_discord_user.mention}")
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

    def get_status_embed(self) -> discord.Embed:
        # embed = discord.Embed(title="Example Title",
        #                       url="https://example.com",
        #                       description="This is an example description. Markdown works too!\n\nhttps://automatic.links\n> Block Quotes\n```\nCode Blocks\n```\n*Emphasis* or _emphasis_\n`Inline code` or ``inline code``\n[Links](https://example.com)\n<@123>, <@!123>, <#123>, <@&123>, @here, @everyone mentions\n||Spoilers||\n~~Strikethrough~~\n**Strong**\n__Underline__",
        #                       colour=0x00b0f4,
        #                       timestamp=datetime.datetime.now())
        embed = discord.Embed(colour=0x00b0f4, timestamp=datetime.datetime.now())

        embed.description = "".join(["# {}\n".format(self.moderated_discord_user.mention),
                                     f"## Trigger reason\n",
                                     f"### {self.moderation_status.trigger_reason.__class__.__name__} \n",
                                     f"## Possible recent messages\n",
                                     "\n".join([f"- {message.message_url}" for message
                                                in self.get_recent_messages_from_user()])
                                     ])

        if self.moderated_discord_user.is_timed_out():
            embed.description += f"\n### Timeout active until <t:{int(self.moderated_discord_user.timed_out_until.timestamp())}:f>\n"
        else:
            embed.description += "\n### ⚠️ Timeout not active ⚠️\n"

        embed.set_author(name=self.discord_bot.user.display_name,
                         icon_url=self.discord_bot.user.display_avatar,
                         url="https://github.com/OriolFilter/discord_simple_link_spam_ratelimit"
                         )

        embed.add_field(name="Was the user preemptively timeout?",
                        value="{}".format(
                            (f"⚠️ No ⚠️. Check if the bot {self.discord_bot.user.mention} can timeout users.",
                             "Yes")[self.moderation_status.preemptive_timeout_applied]),
                        inline=False)

        if self.user_that_removed_timeout:
            embed.add_field(name="Timeout removed by",
                            value=self.user_that_removed_timeout.mention,
                            inline=False)

        if self.user_that_kicked:
            embed.add_field(name="User kicked by",
                            value=self.user_that_kicked.mention,
                            inline=False)

        if self.user_that_banned:
            embed.add_field(name="User banned by",
                            value=self.user_that_banned.mention,
                            inline=False)

        return embed
        # return (f"# Preemtive timeout {self.moderated_discord_user.mention}\n"
        #         f"## Timout hours: {self.config.timeout_hours}\n"
        #         f"If you believe this is was a mistake, please contact the moderators/admins.\n")

    def get_status_text(self) -> str:
        message = "".join([
            f"> If this message is diplayed it's due the bot {self.discord_bot.user.mention} doesn't have permissions to attach embed messages in the channel\n\n",

            "# {}\n".format(self.moderated_discord_user.mention),
            f"## Trigger reason\n",
            f"### {self.moderation_status.trigger_reason.__class__.__name__} \n",
            f"## Possible recent messages\n",
            "\n".join([f"- {message.message_url}" for message
                       in self.get_recent_messages_from_user()]),
        ])
        if self.moderated_discord_user.is_timed_out():
            message += f"\n### Timeout active until <t:{int(self.moderated_discord_user.timed_out_until.timestamp())}:f>\n"
        else:
            message += "\n### ⚠️ Timeout not active ⚠️\n"

        message += "\n### Was the user preemptively timeout?\n"

        if self.moderation_status.preemptive_timeout_applied:
            message += "Yes"
        else:
            message += f"⚠️ No ⚠️. Check if the bot {self.discord_bot.user.mention} can timeout users."

        if self.user_that_removed_timeout:
            message += f"\n ## Timeout removed by {self.user_that_removed_timeout.mention}"

        if self.user_that_kicked:
            message += f"\n ## User kicked by {self.user_that_kicked.mention}"

        if self.user_that_banned:
            message += f"\n ## User banned by {self.user_that_banned.mention}"

        print("!!")
        print(message)
        return message

    def get_recent_messages_from_user(self) -> [MessageRecord]:
        self.recent_messages_storage = list(dict.fromkeys(self.recent_messages_storage +
                                                          self.discord_bot.get_recent_messages_from_user(
                                                              self.moderated_discord_user.id)))

        return self.recent_messages_storage

    def get_mentions(self) -> [str]:
        mention_list = []

        if len(self.config.moderation_roles) > 0:
            for role_id in self.config.moderation_roles:
                mention_list.append(f"<@&{role_id}>")
        else:
            for user in self.moderation_status.users_to_mention:
                mention_list.append(user.mention)
        return mention_list

        # embed.add_field(name="Role Mentions",
        #                 value="\n".join([f"++ <@&{role_id}>" for role_id in self.config.moderation_roles]),
        #                 inline=True)
