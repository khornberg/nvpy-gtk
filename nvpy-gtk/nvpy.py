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

        # Try to connect to the notes database
        # Moved to view.py

        # End init for Controller




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

        # self.notes_list_model_fill()
        # Fill the model for the list
        nvpyView = view.nvpyView(self.config)

        # v = view.nvpyView(self.notes_db)


        # print self.notes_list_model.list

        # show the ui
        view.show()

        # Save before exit
        # from observer_view_close part of Controller class in nvpy.py.bak

        nvpyView.notes_list.close()



def main():
    controller = Controller()
    controller.main_loop()


if __name__ == '__main__':
    main()
