import discord

from typing import Union, Type
from MessagesClasses import *
from ConfigClasses import *


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
    """Class used to keep track of the moderation status. Used to craft the messages to send."""
    preemptive_timeout_applied: bool = False
    user_kicked: bool = False  # Unused
    user_banned: bool = False  # Unused

    trigger_reason = ExceededSameLinkRateLimit | ExceededTotalLinksRateLimit
    possible_recent_messages = [MessageRecord]

    # roles_to_mention = [int] # Redundant, use self.config.moderation_roles
    users_to_mention = [discord.User]


class ModerationEmbedClass(discord.ui.View):
    # Maybe do a moderation embed message that also sets who updated/moderated the bot etc. # TODO
    # Maybe can make use of `original_response_message` for that
    # Maybe use an embed for more fancy info display? IDK
    allowed_moderation_roles: [int]
    moderated_discord_user: Union[discord.User, discord.Member]
    disabled = False
    config = Config
    moderation_status = ModerationStatus

    def __init__(self, moderated_discord_user: Union[discord.User, discord.Member], allowed_moderation_roles: [int],
                 config: Config,
                 moderation_status: ModerationStatus,
                 discord_bot_info: discord.ClientUser,
                 timeout=1200,  # 20 minutes
                 ):
        self.allowed_moderation_roles = allowed_moderation_roles
        self.moderated_discord_user = moderated_discord_user
        self.config = config
        self.moderation_status = moderation_status
        self.discord_bot_info = discord_bot_info
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
                await interaction.message.reply(
                    f"User {interaction.user.mention} removed the timeout for {self.moderated_discord_user.mention}")
            except discord.errors.Forbidden:
                await interaction.message.reply(
                    f"I (bot) don't have enough permissions to **TIMEOUT** {self.moderated_discord_user.mention} (being able to timeout is required to un-timeout).")
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

    def get_status_message(self) -> str:
        # TODO remove
        return (f"# Preemtive timeout {self.moderated_discord_user.mention}\n"
                f"## Timout hours: {self.config.timeout_hours}\n"
                f"If you believe this is was a mistake, please contact the moderators/admins.\n")

    def get_status_embed(self) -> discord.Embed:
        # embed = discord.Embed(title="Example Title",
        #                       url="https://example.com",
        #                       description="This is an example description. Markdown works too!\n\nhttps://automatic.links\n> Block Quotes\n```\nCode Blocks\n```\n*Emphasis* or _emphasis_\n`Inline code` or ``inline code``\n[Links](https://example.com)\n<@123>, <@!123>, <#123>, <@&123>, @here, @everyone mentions\n||Spoilers||\n~~Strikethrough~~\n**Strong**\n__Underline__",
        #                       colour=0x00b0f4,
        #                       timestamp=datetime.datetime.now())
        embed = discord.Embed(colour=0x00b0f4, timestamp=datetime.datetime.now())

        embed.set_author(name=self.discord_bot_info.name,
                         # url="https://example.com" # TODO set image
                         )
        embed.description = f"# {self.moderated_discord_user.mention}"
        embed.add_field(name="Trigger reason",
                        value=str(self.moderation_status.trigger_reason),
                        inline=True)
        # embed.add_field(name="The second inline field.",
        #                 value="Inline fields are stacked next to each other.",
        #                 inline=True)
        # embed.add_field(name="The third inline field.",
        #                 value="You can have up to 3 inline fields in a row.",
        #                 inline=True)
        # embed.add_field(name="Mentions",

        if len(self.moderation_status.users_to_mention) > 0:
            embed.add_field(name="User Mentions",
                            value="\n".join([f"++ {user.mention}" for user in self.moderation_status.users_to_mention]),
                            inline=True)

        if len(self.config.moderation_roles) > 0:
            embed.add_field(name="Role Mentions",
                            value="\n".join([f"++ <@&{role_id}>" for role_id in self.config.moderation_roles]),
                            inline=True)

        embed.set_image(url="https://cubedhuang.com/images/alex-knight-unsplash.webp")

        embed.set_thumbnail(url="https://dan.onl/images/emptysong.jpg")

        embed.set_footer(text="Example Footer",
                         icon_url="https://slate.dan.onl/slate.png")

        return embed
        # return (f"# Preemtive timeout {self.moderated_discord_user.mention}\n"
        #         f"## Timout hours: {self.config.timeout_hours}\n"
        #         f"If you believe this is was a mistake, please contact the moderators/admins.\n")
