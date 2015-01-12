#!/usr/bin/python
from gi.repository import Gtk

class GridWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="nvPY - Gtk")

        self.set_default_size(1200, 700)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        search = Gtk.Entry()
        search.set_text("Search me")
        self.grid.attach(search, 0, 0, 3, 1)

        text = self.create_textview()

        tree = self.create_listbox()

        statusbar = self.create_statusbar()

        menu = self.create_menu()

        # self.grid.attach(scrolledwindow, 1, 1, 3, 1)
        self.grid.attach(tree, 0, 1, 1, 1)
        self.grid.attach_next_to(text, tree, Gtk.PositionType.RIGHT, 2, 1)
        self.grid.attach(statusbar, 0, 2, 1, 1)
        self.grid.attach(menu, 0, 1, 1, 1)

        self.create_app_indicator('/usr/share/icons/Numix-Circle-Light/48x48/apps/notes.svg')

    def create_textview(self):
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)


        self.textview = Gtk.TextView()
        self.textbuffer = self.textview.get_buffer()
        self.textbuffer.set_text("This is some text inside of a Gtk.TextView. "
            + "Select text and click one of the buttons 'bold', 'italic', "
            + "or 'underline' to modify the text accordingly.")
        scrolledwindow.add(self.textview)

        return scrolledwindow

    def create_listbox(self):
        store = Gtk.ListStore(str, str)
        treeiter = store.append(["note1 first line", "08:00"])
        treeiter = store.append(["note2 first line", "08:10"])
        treeiter = store.append(["note3 first line that is really longggggggggggg", "08:20"])

        tree = Gtk.TreeView(store)
        tree.set_headers_visible(False)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Note", renderer, text=0)
        tree.append_column(column)


        return tree

    def create_statusbar(self):
        hbox = Gtk.Box(spacing=10)
        hbox.set_homogeneous(False)

        label = Gtk.Label("This is a normal label")
        hbox.pack_start(label, True, True, 0)

        label = Gtk.Label()
        label.set_text("This is a left-justified label.")
        label.set_justify(Gtk.Justification.LEFT)
        hbox.pack_start(label, True, True, 0)

        return hbox

    def create_menu(self):
        UI_INFO = """
        <ui>
          <menubar name='MenuBar'>
            <menu action='FileMenu'>
              <menuitem action='FileQuit' />
            </menu>
          </menubar>
        </ui>
        """

        action_group = Gtk.ActionGroup("my_actions")

        self.add_file_menu_actions(action_group)

        uimanager = Gtk.UIManager()

        # Throws exception if something went wrong
        uimanager.add_ui_from_string(UI_INFO)

        uimanager.insert_action_group(action_group)

        menubar = uimanager.get_widget("/MenuBar")

        return menubar

    def add_file_menu_actions(self, action_group):
        action_filemenu = Gtk.Action("FileMenu", "File", None, None)
        action_group.add_action(action_filemenu)

        action_filequit = Gtk.Action("FileQuit", None, None, Gtk.STOCK_QUIT)
        action_filequit.connect("activate", self.on_menu_file_quit)
        action_group.add_action(action_filequit)

    def on_menu_file_quit(self, widget):
        Gtk.main_quit()

    def create_app_indicator(self, iconname):
        self.menu = Gtk.Menu()

        APPIND_SUPPORT = 1
        try: from gi.repository import AppIndicator3
        except: APPIND_SUPPORT = 0

        if APPIND_SUPPORT == 1:
            self.ind = AppIndicator3.Indicator.new("nvpy", iconname, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.ind.set_status (AppIndicator3.IndicatorStatus.ACTIVE)
            self.ind.set_menu(self.menu)
        else:
            self.myStatusIcon = Gtk.StatusIcon()
            self.myStatusIcon.set_from_icon_name(iconname)
            self.myStatusIcon.connect('popup-menu', self.right_click_event_statusicon)


win = GridWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()