"""
A simple progress bar to monitor MCMC sampling progress.
Modified from original code by Corey Goldberg (2010)
"""

from __future__ import print_function

import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)
import sys
import time
import datetime
import uuid
try:
    __IPYTHON__
    from IPython.core.display import HTML, Javascript, display
except (NameError, ImportError):
    pass

__all__ = ['progress_bar']


class ProgressBar(object):

    def __init__(self, iterations, animation_interval=.5):
        self.iterations = iterations
        self.start = time.time()
        self.last = 0
        self.animation_interval = animation_interval

    def percentage(self, i):
        return 100 * i / float(self.iterations)

    def update(self, i):
        elapsed = time.time() - self.start
        i += 1

        if elapsed - self.last > self.animation_interval:
            self.animate(i, elapsed)
            self.last = elapsed
        elif i == self.iterations and i != 1:
            self.animate(i, elapsed)


class TextProgressBar(ProgressBar):

    def __init__(self, iterations, printer):
        self.fill_char = '-'
        self.width = 20
        self.printer = printer

        super(TextProgressBar, self).__init__(iterations)
        self.update(0)

    def animate(self, i, elapsed):
        self.printer(self.progbar(i, elapsed))

    def progbar(self, i, elapsed):
        bar = self.bar(self.percentage(i))
        sps = i / float(elapsed)
        eta = (self.iterations / sps) - elapsed
        its = self.iterations

        prog_str = "[{bar}] {it} of {its} in {s_elapsed} sec. " \
                   "| SPS: {sps} | ETA: {eta}" \
                   "".format(bar=bar, it=i, its=its,
                             s_elapsed=round(elapsed, 1),
                             sps=round(sps, 1), eta=round(eta, 1))

        return(prog_str)

    def bar(self, percent):
        all_full = self.width - 2
        num_hashes = int(percent / 100 * all_full)

        bar = self.fill_char * num_hashes + ' ' * (all_full - num_hashes)

        info = '%d%%' % percent
        loc = (len(bar) - len(info)) // 2
        return replace_at(bar, info, loc, loc + len(info))


def replace_at(str, new, start, stop):
    return(str[:start] + new + str[stop:])


def consoleprint(s):
    if sys.platform.lower().startswith('win'):
        print(s, '\r', end='')
    else:
        print(s)


def ipythonprint(s):
    print('\r', s, end='')
    sys.stdout.flush()


class IPythonNotebookPB(ProgressBar):

    def __init__(self, iterations):
        self.divid = str(uuid.uuid4())
        self.sec_id = str(uuid.uuid4())

        pb = HTML(
            """
            <div style="float: left; border: 1px solid black; width:500px">
              <div id="%s" style="background-color:blue; width:0%%">&nbsp;</div>
            </div>
            <label id="%s" style="padding-left: 10px;" text = ""/>
            """ % (self.divid, self.sec_id))
        display(pb)

        super(IPythonNotebookPB, self).__init__(iterations)

    def animate(self, i, elapsed):
        percentage = int(self.fraction(i))

        display(Javascript(
            "$('div#%s').width('%i%%')" % (self.divid, percentage)))
        display(Javascript("$('label#%s').text('%i%% in %.1f sec')" %
                           (self.sec_id, fraction, round(elapsed, 1))))


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


def progress_bar(iters):
    if run_from_ipython():
        if None:
            return NotebookProgressBar(iters)
        else:
            return TextProgressBar(iters, ipythonprint)
    else:
        return TextProgressBar(iters, consoleprint)
