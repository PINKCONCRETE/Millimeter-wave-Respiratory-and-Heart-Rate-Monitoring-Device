class BroadcastingQueue:
    """
    A wrapper around multiple queues that broadcasts put operations to all of them.
    Used to duplicate data streams for multiple consumers (e.g., Database and IPC).
    """
    def __init__(self, queues):
        self.queues = queues

    def put(self, item, block=True, timeout=None):
        for q in self.queues:
            q.put(item, block=block, timeout=timeout)
    
    def put_nowait(self, item):
        for q in self.queues:
            q.put_nowait(item)

    def qsize(self):
        return self.queues[0].qsize() if self.queues else 0

    def empty(self):
        return self.queues[0].empty() if self.queues else True

    def full(self):
        return self.queues[0].full() if self.queues else False
