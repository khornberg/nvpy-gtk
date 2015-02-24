import utils
from utils import KeyValueObject, SubjectMixin
from notes_db import NotesDB, SyncError, ReadError, WriteError

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

    def get_idx(self, key):
        """Find idx for passed LOCAL key.
        """
        found = [i for i, e in enumerate(self.list) if e.key == key]
        if found:
            return found[0]

        else:
            return -1

# Class to interact with the model and notes list from the ui
# This is passed a Gtk.ListStore for the actual model
#
# Simple note is optional
# notes_db is the database class
# NotesListModel is a list of key, dict for the notes
# NotesList is a set of helpers for the ui to interact with to get data
#
# [simplenote] => notes_db => NotesListModel => NotesList
class NotesList():

    def __init__(self, config, list_store):
        self.config = config
        self.notes_list_model = NotesListModel()
        self.model = list_store

        # read our database of notes into memory
        # and sync with simplenote.
        try:
            self.notes_db = NotesDB(config)

        except ReadError, e:
            emsg = "Please check nvpy.log.\n" + str(e)
            print 'Sync error: %s' % emsg
            # self.view.show_error('Sync error', emsg)
            exit(1)

    def fill(self, search_string=None):
        # nn is a list of (key, note) objects
        nn, match_regexp, active_notes = self.notes_db.filter_notes(search_string)
        # this will trigger the list_change event
        self.notes_list_model.set_list(nn)
        self.notes_list_model.match_regexp = match_regexp

        # import pickle
        # print pickle.dumps(nn)

        # gets the id or key of single note
        # print self.notes_list_model.get_idx('b4f709b924b6401c4cbb354771a531')

        # list is an array of objects with key and note
        # note is a dict
        # print pickle.dumps(self.notes_list_model.list[6].note)
        # print self.notes_list_model.list[6].note['content']
        # print self.notes_list_model.list[6].key

        # necessary to clear the model for searching
        self.model.clear()

        for n in self.notes_list_model.list:
            # i = self.notes_list_model.list.index(n)
            self.model.append(self.create_list_item(n))


        print len(nn), len(self.notes_db.notes)
        return len(nn)

    def create_list_item(self, n):
        title_snippet = utils.get_note_title(n.note)
        modifydate = utils.human_date(n.note['modifydate'])
        tags = utils.sanitise_tags(', '.join(n.note['tags'])) # sanitise tags
        pinned = utils.note_pinned(n.note)

        string_of_tags = ', '.join(tags) # join tags for display; could be moved to utils

        return [title_snippet, modifydate, string_of_tags, pinned, n.key]

    def get_note(self, key):
        idx = self.notes_list_model.get_idx(key)

        if idx == -1:
            return False

        return self.notes_list_model.list[idx].note

    def search_note_title(self, search_string=None):
        # simple search by iterating through all of the notes...
        for k in self.notes_db.notes:
            n = self.notes_db.notes[k]
            # we don't do anything with deleted notes (yet)
            if n.get('deleted'):
                continue

            title = utils.get_note_title_search(n)
            if (search_string == title):
                return utils.KeyValueObject(key=k, note=n, tagfound=0)

        return None

    def close(self):
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