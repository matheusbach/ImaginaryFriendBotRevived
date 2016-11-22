import random

from telegram import Update
from telegram.ext import Handler

from src.domain.command import Command
from src.entity.chat import Chat
from src.entity.pair import Pair
from src.entity.reply import Reply
from src.entity.word import Word


class CommandHandler(Handler):
    def __init__(self, message_sender):
        super(CommandHandler, self).__init__(self.handle)
        self.commands = {
            'start':      self.__start_command,
            'help':       self.__help_command,
            'ping':       self.__ping_command,
            'set_chance': self.__set_chance_command,
            'get_chance': self.__get_chance_command,
            'get_stats':  self.__get_stats_command,
            'moderate':   self.__moderate_command
        }
        self.message_sender = message_sender

    def check_update(self, update):
        if isinstance(update, Update) and update.message:
            message = update.message

            return message.text and message.text.startswith('/') and Command.parse_name(message) in self.commands
        else:
            return False

    def handle_update(self, update, dispatcher):
        optional_args = self.collect_optional_args(dispatcher, update)

        return self.callback(dispatcher.bot, update, **optional_args)

    def handle(self, bot, update):
        chat = Chat.get_chat(update.message)
        command = Command(chat=chat, message=update.message)

        try:
            if command.name == 'moderate':
                self.commands['moderate'](bot, command)
            else:
                self.commands[command.name](command)
        except (IndexError, ValueError):
            self.message_sender.reply(command, 'Invalid command! Type /help')

    def __start_command(self, command):
        self.message_sender.reply(command, 'Hi! :3')

    def __help_command(self, command):
        self.message_sender.reply(
            command,
            """Add me to your group and let me listen to your chat for a while.
When I learn enough word pairs, I'll start bringing fun and absurdity to your conversations.

Available commands:
• /ping,
• /get_stats: get the number of word pairs I've learned in this chat,
• /set_chance: set the chance that I'll reply to a random message (must be in range 1-50, default: 5),
• /get_chance: get the current chance of my random reply.

If you get tired of me, you can kick me from the group.
In 12 hours, I'll forget everything that have been learned in your chat, so you can add me again and teach me new things!
"""
        )

    def __ping_command(self, command):
        answers = [
            'echo',
            'pong',
            'ACK',
            'reply',
            'pingback'
        ]

        self.message_sender.reply(command, random.choice(answers))

    def __set_chance_command(self, command):
        try:
            random_chance = int(command.args[0])

            if random_chance < 1 or random_chance > 50:
                raise ValueError

            command.chat.update(random_chance=random_chance)

            self.message_sender.reply(command, 'Set chance to: {}'.format(random_chance))
        except (IndexError, ValueError):
            self.message_sender.reply(command, 'Usage: /set_chance 1-50.')

    def __get_chance_command(self, command):
        self.message_sender.reply(command, 'Current chance: {}'.format(command.chat.random_chance))

    def __get_stats_command(self, command):
        self.message_sender.reply(command, 'Pairs: {}'.format(command.chat.pairs().count()))

    def __moderate_command(self, bot, command):
        try:
            def is_admin():
                user_id = command.message.from_user.id
                admin_ids = list(map(
                    lambda member: member.user.id,
                    bot.get_chat_administrators(chat_id=command.chat.telegram_id)
                ))

                return user_id in admin_ids

            def generate_list(words):
                list = []
                for k, v in words.items():
                    list.append("- %s : %d" % (v, k))

                return '\n'.join(list)

            def find_pairs(chat_id, word_ids):
                return Pair.where('chat_id', chat_id) \
                    .where(
                        Pair.query().where_in('first_id', word_ids)
                            .or_where_in('second_id', word_ids)
                    ) \
                    .get()

            def find_current_chat_words(search_word):
                found_words = Word.where('word', 'like', search_word + '%') \
                    .order_by('word', 'asc') \
                    .limit(10) \
                    .lists('word', 'id')

                if len(found_words) == 0:
                    return []

                to_keep = []
                for pair in find_pairs(command.chat.id, list(found_words.keys())):
                    if pair.first_id in found_words:
                        to_keep.append(pair.first_id)
                    if pair.second_id in found_words:
                        to_keep.append(pair.second_id)

                to_keep = set(to_keep)

                return dict((k, found_words[k]) for k in found_words if k in to_keep)

            if not is_admin():
                return self.message_sender.reply(command, 'You don\'t have admin privileges!')

            if len(command.args) == 2:
                pairs_ids = find_pairs(command.chat.id, [command.args[1]]).lists('id')

                Pair.where_in('id', pairs_ids).delete()
                Reply.where_in('pair_id', pairs_ids).delete()
            else:
                found_words = find_current_chat_words(command.args[0])

                if len(found_words) == 0:
                    self.message_sender.reply(command, 'No words found!')
                else:
                    self.message_sender.reply(command, generate_list(found_words))
        except (IndexError, ValueError):
            self.message_sender.reply(command, """Usage:
/moderate <word> for search
/moderate <word> <word_id> for deletion""")

