#!/usr/bin/python
from gi.repository import Gtk, Gdk, Pango
import os
import utils

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

    def __init__(self, notes_list_model, list_store):
        self.notes_list_model = notes_list_model
        self.model = list_store

    def fill(self):
        # import pickle
        # print pickle.dumps(nn)

        # gets the id or key of single note
        # print self.notes_list_model.get_idx('b4f709b924b6401c4cbb354771a531')

        # list is an array of objects with key and note
        # note is a dict
        # print pickle.dumps(self.notes_list_model.list[6].note)
        # print self.notes_list_model.list[6].note['content']
        # print self.notes_list_model.list[6].key

        for n in self.notes_list_model.list:
            i = self.notes_list_model.list.index(n)

            title_snippet = utils.get_note_title(n.note)
            modifydate = utils.human_date(n.note['modifydate'])
            tags = utils.sanitise_tags(', '.join(n.note['tags'])) # sanitise tags
            pinned = utils.note_pinned(n.note)

            string_of_tags = ', '.join(tags) # join tags for display; could be moved to utils

            self.model.append([title_snippet, modifydate, string_of_tags, pinned, n.key])


        # print len(nn), len(self.notes_db.notes)

    def get_note(self, key):
        idx = self.notes_list_model.get_idx(key)
        return self.notes_list_model.list[idx].note


class nvpyView(Gtk.Window):

    def __init__(self, notes_list_model):
        # Map handlers from glade ui
        handlers = {
            'gtk_main_quit': Gtk.main_quit,
            'search_notes': self.refresh_filter,
            'show_note': self.show_note,
        }

        # Build ui from glade file
        self.builder = Gtk.Builder()
        self.builder.add_from_file('ui.glade')
        self.builder.connect_signals(handlers)

        # notes list model, class NotesListModel from nvpy.py
        # Populate model
        #                                                           title, modtime, tags, pinned key
        self.notes_list = NotesList(notes_list_model, Gtk.ListStore(str,   str,     str,  bool,  str))
        self.notes_list.fill() # data from notes_list_model which has data from the notes_db

        # Create filter
        self.search_filter = self.notes_list.model.filter_new()
        self.search_filter.set_visible_func(self.search_notes)

        # Connect model to treeview
        self.notes_treeview = self.builder.get_object('treeview1')
        self.notes_treeview.set_model(self.search_filter)

        # Text column
        title_col   = self.builder.get_object('treeviewcolumn1')
        render_text = Gtk.CellRendererText()
        render_text.props.ellipsize = Pango.EllipsizeMode.END
        title_col.pack_start(render_text, True)
        title_col.add_attribute(render_text, 'markup', 0)
        self.notes_treeview.append_column(title_col)

        # Date column
        time_col   = self.builder.get_object('treeviewcolumn2')
        render_text2 = Gtk.CellRendererText()
        # render_text2.props.ellipsize = Pango.EllipsizeMode.END
        time_col.pack_start(render_text2, True)
        time_col.add_attribute(render_text2, 'markup', 1)
        self.notes_treeview.append_column(time_col)

        # Text box
        self.text_view = self.builder.get_object('textview1')

        # Load Styles
        style_provider = Gtk.CssProvider()

        css = """
        #nvpyWindow {
            background-color: #FFF;
        }
        #nvpyNoteList {
            border-bottom-color: #CCC;
            border-bottom-width: 1px;
            border-bottom-style: solid;
        }
        #nvpyNoteList column:nth-child(last) {
            color: #666;
            font-size: 6;
        }
        """

        style_provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


        self.window = self.builder.get_object("window1")

        # Name the window parts for styling
        self.window.set_name("nvpyWindow")
        self.notes_treeview.set_name("nvpyNoteList")

        self.window.show()

    # search notes
    # only kinda works - need to look through and see how the oringial works
    # also need to search the whole model - tags, all text, etc.
    def search_notes(self, model, iter, data=None):
        searchentry1 = self.builder.get_object('searchentry1')
        search_query = searchentry1.get_text()

        print ('search of {}'.format(search_query))

        if search_query == "":
            return True

        for col in range(0,self.notes_treeview.get_n_columns()):
            value = model.get_value(iter, col).lower()
            print ('value of {}'.format(value))
            print (value.find(search_query))
            if value.find(search_query) > 0:
                return True
            else:
                return False

        return False

        # value = model.get_value(iter).lower()
        # return True if value.startswith(search_query) else False

    def refresh_filter(self, widget):
        self.search_filter.refilter()

    def show_note(self, selection):
        key = None

        model, treeiter = selection.get_selected()
        if treeiter != None:
            key = model[treeiter][4]

        note = self.notes_list.get_note(key)
        self.textbuffer = self.text_view.get_buffer()
        self.textbuffer.set_text(note['content'])


def show():
    # Show the ui
    # win = nvpyView(notes_db)
    Gtk.main()
