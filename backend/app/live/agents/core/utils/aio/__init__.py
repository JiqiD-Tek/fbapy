from . import debug, duplex_unix, itertools
from .channel import Chan, ChanClosed, ChanReceiver, ChanSender
from .interval import Interval, interval
from .sleep import Sleep, SleepFinished, sleep
from .task_set import TaskSet
from .utils import cancel_and_wait, gracefully_cancel
from .wait_group import WaitGroup

__all__ = [
    'Chan',
    'ChanClosed',
    'ChanReceiver',
    'ChanSender',
    'Interval',
    'Sleep',
    'SleepFinished',
    'TaskSet',
    'WaitGroup',
    'cancel_and_wait',
    'debug',
    'duplex_unix',
    'gracefully_cancel',
    'interval',
    'itertools',
    'sleep',
]

# Cleanup docs of unexported modules
_module = dir()
NOT_IN_ALL = [m for m in _module if m not in __all__]

__pdoc__ = {}

for n in NOT_IN_ALL:
    __pdoc__[n] = False
