#!/usr/bin/python
from gi.repository import Gtk, Gdk, Pango
import os
import utils
from notes import NotesList, NotesListModel
import re
import webbrowser

class nvpyView(Gtk.Window):

    def __init__(self, config):
        # Map handlers from glade ui
        handlers = {
            'gtk_main_quit': Gtk.main_quit,
            'search_notes': self.search_notes,
            'show_note': self.show_note,
            'motion_notify_event': self.motion_notify_event,
        }

        # Build ui from glade file
        self.builder = Gtk.Builder()
        self.builder.add_from_file('ui.glade')
        self.builder.connect_signals(handlers)

        # notes list model, class NotesListModel from nvpy.py
        # Populate model
        #                                                 title, modtime, tags, pinned key
        self.notes_list = NotesList(config, Gtk.ListStore(str,   str,     str,  bool,  str))
        self.notes_list.fill() # data from notes_list_model which has data from the notes_db

        # Connect model to treeview
        self.notes_treeview = self.builder.get_object('treeview1')
        self.notes_treeview.set_model(self.notes_list.model)

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

        # Tags box
        self.tags = self.builder.get_object('entry1')

        # Pinned checkbox
        self.pin_box = self.builder.get_object('checkbutton1')

        # Load tags
        self.textbuffer = self.text_view.get_buffer()
        self.tag_table = self.textbuffer.get_tag_table()

        highlight_tag = self.tag_table.lookup("highlight")
        if highlight_tag == None:
            self.highlight_tag = self.textbuffer.create_tag("highlight", foreground="#000000", background="#F5F262")

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

        self.select_note()

        self.window.show()

    # search notes
    def search_notes(self, search):
        search_query = search.get_text()

        print ('search of {}'.format(search_query))

        notes = self.notes_list.fill(search_query)

        self.select_note()

    def select_note(self, position=0):
        if len(self.notes_list.notes_list_model.list) > 0:
            self.notes_treeview.set_cursor(position)

    def show_note(self, selection):
        key = None

        model, treeiter = selection.get_selected()
        if treeiter != None:
            key = model[treeiter][4]

            note = self.notes_list.get_note(key)

            # note does not exist
            if note == False:
                self.textbuffer = self.text_view.get_buffer()
                self.textbuffer.set_text('')
                return

            self.textbuffer = self.text_view.get_buffer()
            self.textbuffer.set_text(note['content'])

            searchentry1 = self.builder.get_object('searchentry1')
            search_query = searchentry1.get_text()
            start_iter =  self.textbuffer.get_start_iter()

            # highlight search term
            if search_query != '':
                self.highlight(start_iter, search_query)

            # create links
            self.create_links(start_iter)

            # show tags
            self.show_tags(note)

            # toggle pinned
            self.pin(note)

    def highlight(self, start_iter, search_query):
        found = start_iter.forward_search(search_query, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
        if found:
            match_start, match_end = found
            self.textbuffer.apply_tag(self.highlight_tag, match_start, match_end)
            self.highlight(match_end, search_query)

    def create_links(self, start_iter):

        t = self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
        # the last group matches [[bla bla]] inter-note links
        pat = \
        r"\b((https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[A-Za-z0-9+&@#/%=~_|])|(\[\[[^][]*\]\])"

        for mo in re.finditer(pat, t):
            # extract the link from the match object
            if mo.groups()[2] is not None:
                link = mo.groups()[2]
                ul = 0
            else:
                link = mo.groups()[0]
                ul = 1

            print link
            print ul

            found = start_iter.forward_search(link, Gtk.TextSearchFlags.TEXT_ONLY, None)
            if found:
                match_start, match_end = found

                link_tag = self.tag_table.lookup(link)

                if link_tag == None:
                    # Overriding the name and family property for my own purpose
                    # This allows one to cleanly get the url to open instead of doing some monkey text buffer math
                    link_tag = self.textbuffer.create_tag(link, foreground="#0000FF", underline=Pango.Underline.SINGLE)
                    link_tag.set_property('family', 'link')
                    link_tag.connect("event", self.open_url)

                self.textbuffer.apply_tag(link_tag, match_start, match_end)

                start_iter = match_end


    # Modified from https://github.com/gossel-j/CaptainSoul/blob/master/cptsoul/htmltextview.py
    def motion_notify_event(self, widget, event):
        x, y = widget.get_pointer()
        tags = widget.get_iter_at_location(x, y).get_tags()
        for tag in tags:
            if tag.get_property('family') == 'link':
                window = widget.get_window(Gtk.TextWindowType.TEXT)
                window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))

        if tags == []:
            window = widget.get_window(Gtk.TextWindowType.TEXT)
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.XTERM))


    def open_url(self, tag, widget, event, l_iter):
        if event.type == Gdk.EventType.BUTTON_RELEASE:
            # Get the link stored in the text tag property "name"
            # Not the correct use of the property but it works
            url = tag.get_property('name')
            webbrowser.open_new_tab(url)

    def show_tags(self, note):
        self.tags.set_text(', '.join(note['tags']))

    def pin(self, note):
        if 'systemtags' in note.keys() and 'pinned' in note['systemtags']:
            self.pin_box.set_active(True)
        else:
            self.pin_box.set_active(False)

def show():
    # Show the ui
    # win = nvpyView(notes_db)
    Gtk.main()
