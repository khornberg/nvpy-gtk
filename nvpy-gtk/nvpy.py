#!/usr/bin/env python

# nvPY: cross-platform note-taking app with simplenote syncing
# copyright 2012 by Charl P. Botha <cpbotha@vxlabs.com>
# new BSD license

# inspired by notational velocity and nvALT, neither of which I've used,
# and ResophNotes, which I have used.

# full width horizontal bar at top to search
# left column with current results: name, mod date, summary, tags
# right column with text of currently selected note

# * typing in the search bar:
# - press enter: focus jumps to note if ANYTHING is selected. if nothing is
# selected, enter creates a new note with the current string as its name.
# - esc clears the search entry, esc again jumps to list
# - up and down changes currently selected list
# * in note conten area
# - esc goes back to notes list.

# http://www.scribd.com/doc/91277952/Simple-Note-API-v2-1-3
# this also has a sync algorithm!

# 1. finish implementing search
# 1.5. think about other storage formats. What if we want to store more? (cursor position and so on. sqlite?)
# 2. note editing
#   a) saving to disc: remember lmodified or whatever.
#   b) syncing with simplenote

# to check if we're online

import codecs
import ConfigParser
import logging
from logging.handlers import RotatingFileHandler
from notes_db import NotesDB, SyncError, ReadError, WriteError
import os
import sys
import time

from utils import KeyValueObject, SubjectMixin
import view
import webbrowser

try:
    import markdown
except ImportError:
    HAVE_MARKDOWN = False
else:
    HAVE_MARKDOWN = True

try:
    import docutils
    import docutils.core
except ImportError:
    HAVE_DOCUTILS = False
else:
    HAVE_DOCUTILS = True

VERSION = "0.9.4"


class Config:
    """
    @ivar files_read: list of config files that were parsed.
    @ivar ok: True if config files had a default section, False otherwise.
    """
    def __init__(self, app_dir):
        """
        @param app_dir: the directory containing nvpy.py
        """

        self.app_dir = app_dir
        # cross-platform way of getting home dir!
        # http://stackoverflow.com/a/4028943/532513
        home = os.path.abspath(os.path.expanduser('~'))
        defaults = {'app_dir': app_dir,
                    'appdir': app_dir,
                    'home': home,
                    'notes_as_txt': '0',
                    'housekeeping_interval': '2',
                    'search_mode': 'gstyle',
                    'case_sensitive': '1',
                    'search_tags': '1',
                    'sort_mode': '1',
                    'pinned_ontop': '1',
                    'db_path': os.path.join(home, '.nvpy-gtk'),
                    'txt_path': os.path.join(home, '.nvpy-gtk/notes'),
                    'font_family': 'Courier',  # monospaced on all platforms
                    'font_size': '10',
                    'list_font_family': 'Helvetica',  # sans on all platforms
                    'list_font_family_fixed': 'Courier',  # monospace on all platforms
                    'list_font_size': '10',
                    'layout': 'horizontal',
                    'print_columns': '0',
                    'background_color': 'white',
                    'sn_username': '',
                    'sn_password': '',
                    'simplenote_sync': '1',
                    # Filename or filepath to a css file used style the rendered
                    # output; e.g. nvpy.css or /path/to/my.css
                    'rest_css_path': None,
                   }

        cp = ConfigParser.SafeConfigParser(defaults)
        # later config files overwrite earlier files
        # try a number of alternatives
        self.files_read = cp.read([os.path.join(app_dir, 'nvpy.cfg'),
                                   os.path.join(home, 'nvpy.cfg'),
                                   os.path.join(home, '.nvpy.cfg'),
                                   os.path.join(home, '.nvpy'),
                                   os.path.join(home, '.nvpyrc')])

        cfg_sec = 'nvpy'

        if not cp.has_section(cfg_sec):
            cp.add_section(cfg_sec)
            self.ok = False

        else:
            self.ok = True

        # for the username and password, we don't want interpolation,
        # hence the raw parameter. Fixes
        # https://github.com/cpbotha/nvpy/issues/9
        self.sn_username = cp.get(cfg_sec, 'sn_username', raw=True)
        self.sn_password = cp.get(cfg_sec, 'sn_password', raw=True)
        self.simplenote_sync = cp.getint(cfg_sec, 'simplenote_sync')
        # make logic to find in $HOME if not set
        self.db_path = cp.get(cfg_sec, 'db_path')
        #  0 = alpha sort, 1 = last modified first
        self.notes_as_txt = cp.getint(cfg_sec, 'notes_as_txt')
        self.txt_path = os.path.join(home, cp.get(cfg_sec, 'txt_path'))
        self.search_mode = cp.get(cfg_sec, 'search_mode')
        self.case_sensitive = cp.getint(cfg_sec, 'case_sensitive')
        self.search_tags = cp.getint(cfg_sec, 'search_tags')
        self.sort_mode = cp.getint(cfg_sec, 'sort_mode')
        self.pinned_ontop = cp.getint(cfg_sec, 'pinned_ontop')
        self.housekeeping_interval = cp.getint(cfg_sec, 'housekeeping_interval')
        self.housekeeping_interval_ms = self.housekeeping_interval * 1000

        self.font_family = cp.get(cfg_sec, 'font_family')
        self.font_size = cp.getint(cfg_sec, 'font_size')

        self.list_font_family = cp.get(cfg_sec, 'list_font_family')
        self.list_font_family_fixed = cp.get(cfg_sec, 'list_font_family_fixed')
        self.list_font_size = cp.getint(cfg_sec, 'list_font_size')

        self.layout = cp.get(cfg_sec, 'layout')
        self.print_columns = cp.getint(cfg_sec, 'print_columns')

        self.background_color = cp.get(cfg_sec, 'background_color')

        self.rest_css_path = cp.get(cfg_sec, 'rest_css_path')


class NotesListModel(SubjectMixin):
    """
    @ivar list: List of (str key, dict note) objects.
    """
    def __init__(self):
        # call mixin ctor
        SubjectMixin.__init__(self)

        self.list = []
        self.match_regexps = []

    def set_list(self, alist):
        self.list = alist
        self.notify_observers('set:list', None)

    def get_idx(self, key):
        """Find idx for passed LOCAL key.
        """
        found = [i for i, e in enumerate(self.list) if e.key == key]
        if found:
            return found[0]

        else:
            return -1


class Controller:
    """Main application class.
    """

    def __init__(self):
        # setup appdir
        if hasattr(sys, 'frozen') and sys.frozen:
            self.appdir, _ = os.path.split(sys.executable)

        else:
            dirname = os.path.dirname(__file__)
            if dirname and dirname != os.curdir:
                self.appdir = dirname
            else:
                self.appdir = os.getcwd()

        # make sure it's the full path
        self.appdir = os.path.abspath(self.appdir)

        # should probably also look in $HOME
        self.config = Config(self.appdir)
        self.config.app_version = VERSION

        # configure logging module
        #############################

        # first create db directory if it doesn't exist yet.
        if not os.path.exists(self.config.db_path):
            os.mkdir(self.config.db_path)

        log_filename = os.path.join(self.config.db_path, 'nvpy.gtk.log')
        # file will get nuked when it reaches 100kB
        lhandler = RotatingFileHandler(log_filename, maxBytes=100000, backupCount=1)
        lhandler.setLevel(logging.DEBUG)
        lhandler.setFormatter(logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s'))
        # we get the root logger and configure it
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(lhandler)
        # this will go to the root logger
        logging.debug('nvpy logging initialized')

        logging.debug('config read from %s' % (str(self.config.files_read),))

        if self.config.sn_username == '':
            self.config.simplenote_sync = 0

        css = self.config.rest_css_path
        if css:
            if css.startswith("~/"):
                # On Mac, paths that start with '~/' aren't found by path.exists
                css = css.replace(
                    "~", os.path.abspath(os.path.expanduser('~')), 1)
                self.config.rest_css_path = css
            if not os.path.exists(css):
                # Couldn't find the user-defined css file. Use docutils css instead.
                self.config.rest_css_path = None

        self.notes_list_model = NotesListModel()

        # read our database of notes into memory
        # and sync with simplenote.
        try:
            self.notes_db = NotesDB(self.config)

        except ReadError, e:
            emsg = "Please check nvpy.log.\n" + str(e)
            print 'Sync error: %s' % emsg
            # self.view.show_error('Sync error', emsg)
            exit(1)


        # End init for Controller

    def helper_save_sync_msg(self):

        # Saving 2 notes. Syncing 3 notes, waiting for simplenote server.
        # All notes saved. All notes synced.

        saven = self.notes_db.get_save_queue_len()

        if self.config.simplenote_sync:
            syncn = self.notes_db.get_sync_queue_len()
            wfsn = self.notes_db.waiting_for_simplenote
        else:
            syncn = wfsn = 0

        savet = 'Saving %d notes.' % (saven,) if saven > 0 else ''
        synct = 'Waiting to sync %d notes.' % (syncn,) if syncn > 0 else ''
        wfsnt = 'Syncing with simplenote server.' if wfsn else ''

        return ' '.join([i for i in [savet, synct, wfsnt] if i])

    # fill up the model with the data from the notes_db from nvpy
    def notes_list_model_fill(self):
        # nn is a list of (key, note) objects
        nn, match_regexp, active_notes = self.notes_db.filter_notes()
        # this will trigger the list_change event
        self.notes_list_model.set_list(nn)
        self.notes_list_model.match_regexp = match_regexp


    def main_loop(self):
        if not self.config.files_read:
            self.view.show_warning('No config file',
                                  'Could not read any configuration files. See https://github.com/cpbotha/nvpy for details.')

        elif not self.config.ok:
            wmsg = ('Please rename [default] to [nvpy] in %s. ' + \
                    'Config file format changed after nvPY 0.8.') % \
            (str(self.config.files_read),)
            self.view.show_warning('Rename config section', wmsg)


        # Test creation of notes programically for importing
        #
        # print 'Old notes'
        # import pprint
        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(self.notes_db.notes)
        # print '------------------------------------'

        # print 'New notes'
        # key = self.notes_db.create_note('new note created')
        # print 'key: %s' % key
        # note = self.notes_db.get_note(key)
        # print 'note: %s' % note
        # self.notes_db.set_note_content(key, 'Some new content witha  spelling mistake')
        # note = self.notes_db.get_note(key)
        # print 'note: %s' % note
        # self.notes_db.set_note_tags(key, 'tag1')
        # note = self.notes_db.get_note(key)
        # print 'saving single note'
        # self.notes_db.helper_save_note(key, note)
        self.notes_list_model_fill()
        # Fill the model for the list
        view.nvpyView(self.notes_list_model)

        # v = view.nvpyView(self.notes_db)


        # print self.notes_list_model.list

        # show the ui
        view.show()

        # Save before exit
        # from observer_view_close part of Controller class in nvpy.py.bak

        # check that everything has been saved and synced before exiting

        # first make sure all our queues are up to date
        self.notes_db.save_threaded()
        if self.config.simplenote_sync:
            self.notes_db.sync_to_server_threaded(wait_for_idle=False)
            syncn = self.notes_db.get_sync_queue_len()
            wfsn = self.notes_db.waiting_for_simplenote
        else:
            syncn = wfsn = 0

        # then check all queues
        saven = self.notes_db.get_save_queue_len()

        # if there's still something to do, warn the user.
        if saven or syncn or wfsn:
            msg = "Are you sure you want to exit? I'm still busy: " + self.helper_save_sync_msg()
            really_want_to_exit = False #force save not connected to the view self.view.askyesno("Confirm exit", msg)

            if really_want_to_exit:
                # self.view.close()
                # print 'note: %s' % note
                print 'closing'

        else:
            # self.view.close()
            print 'closing'



def main():
    controller = Controller()
    controller.main_loop()


if __name__ == '__main__':
    main()
