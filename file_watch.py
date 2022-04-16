import time

from os.path import dirname
from threading import Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FileWatcher:
    """Simple class to handle the life time of a file watch.

    Args:
        files (iterable): set of files to watch
        callback (callable): callback function /method to call on a change
    """
    def __init__(self, files, callback):
        self.observer = Observer()
        for file_path in files:
            watch_dir = dirname(file_path)
            self.observer.schedule(Handler(file_path, callback),
                                   watch_dir,
                                   recursive=False)
        self.observer.start()

    def shutdown(self):
        self.observer.unschedule_all()
        self.observer.stop()


class Handler(FileSystemEventHandler):
    """Filesystem event handler calling a callback on a change to the file.

    Args:
        file_path (str): path to the file that shall be observed for changes
        callback (callable): function / method to call when a change occurs
    """
    def __init__(self, file_path, callback):
        super().__init__()
        self._callback = callback
        self._file_path = file_path
        self.lock = Lock()
        self.last_change = 0

    def on_any_event(self, event):
        """Override of event handling method."""
        if (not event.is_directory and
                event.event_type in ('created', 'modified') and
                event.src_path == self._file_path):
            # Limit the frequency of the updates
            # This handles a case where a single save causes several events
            with self.lock:
                if time.monotonic() - self.last_change > 0.3:
                    self.last_change = time.monotonic()
                    time.sleep(0.1)
                    self._callback(event.src_path)
