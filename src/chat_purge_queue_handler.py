import logging
from telegram.ext import Job
from src.domain.chat import Chat


class ChatPurgeQueueHandler:
    queue = None
    default_interval = 99999.0
    jobs = {}

    # TODO. Должно взять все задачи из таблицы и проинициализировать их
    def init(self, queue, default_interval):
        self.queue = queue
        self.default_interval = float(default_interval)

    def add(self, chat_id, interval=None):
        if interval is None:
            interval = self.default_interval
        if self.queue is None:
            logging.error("Queue is not set!")
            return

        logging.info("Added chat #%d to purge queue, with interval %d" %
                     (chat_id, interval))

        job = self.__make_purge_job(chat_id, interval)
        self.jobs[chat_id] = job
        self.queue.put(job)

    def remove(self, chat_id):
        if self.queue is None:
            logging.error("Queue is not set!")
            return
        if chat_id not in self.jobs:
            return

        logging.info("Removed chat #%d from purge queue" % chat_id)

        job = self.jobs.pop(chat_id)
        job.schedule_removal()

    def __make_purge_job(self, chat_id, interval=None):
        if interval is None:
            interval = self.default_interval

        return Job(self.__purge_callback, interval, repeat=False, context=chat_id)

    def __purge_callback(self, bot, job):
        chat_id = job.context
        logging.info("Removing chat #%d data..." % chat_id)

        chat = Chat.find(job.context)
        if chat is not None:
            chat.pairs().delete()
            chat.delete()
