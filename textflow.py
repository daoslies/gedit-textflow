from gi.repository import GObject, Gedit, Gtk
import re

class TextFlowPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "TextFlowPlugin"
    window = GObject.Property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._handlers = {}
        self._tags_created = set()

    def do_activate(self):
        print("TextFlow activated!")
        self._handlers['tab-added'] = self.window.connect('tab-added', self.on_tab_added)
        
        for doc in self.window.get_documents():
            self.connect_document(doc)

    def do_deactivate(self):
        print("TextFlow deactivated!")
        for handler_id in self._handlers.values():
            self.window.disconnect(handler_id)
        self._handlers.clear()

    def do_update_state(self):
        pass

    def on_tab_added(self, window, tab):
        doc = tab.get_document()
        self.connect_document(doc)

    def connect_document(self, doc):
        doc.connect('changed', self.on_document_changed)
        self.setup_tags(doc)
        print(f"Connected to document")

    def setup_tags(self, doc):
        """Create text tags for coloring"""
        tag_table = doc.get_tag_table()
        
        # Only create tags once per document
        doc_id = id(doc)
        if doc_id in self._tags_created:
            return
        
        # Create a tag for task items (lines starting with --)
        if not tag_table.lookup('task-item'):
            tag = doc.create_tag('task-item', foreground='#3584e4')  # Nice blue
            print("Created task-item tag")
        
        # Create a tag for completed items (containing "tick" or "Tick")
        if not tag_table.lookup('completed-item'):
            tag = doc.create_tag('completed-item', foreground='#26a269')  # Green
            print("Created completed-item tag")
        
        self._tags_created.add(doc_id)

    def on_document_changed(self, doc):
        """Called whenever the document text changes"""
        start = doc.get_start_iter()
        end = doc.get_end_iter()
        text = doc.get_text(start, end, False)
        
        # Remove all existing tags first
        doc.remove_tag_by_name('task-item', start, end)
        doc.remove_tag_by_name('completed-item', start, end)
        
        # Parse and apply tags
        self.apply_highlighting(doc, text)

    def apply_highlighting(self, doc, text):
        """Find task patterns and apply colored tags"""
        lines = text.split('\n')
        char_offset = 0
        
        for line in lines:
            # Check if line starts with --
            if line.strip().startswith('--'):
                # Get iterators for this line
                start_iter = doc.get_iter_at_offset(char_offset)
                end_iter = doc.get_iter_at_offset(char_offset + len(line))
                
                # Check if it's completed (contains "tick" or "Tick")
                if 'tick' in line.lower():
                    doc.apply_tag_by_name('completed-item', start_iter, end_iter)
                else:
                    doc.apply_tag_by_name('task-item', start_iter, end_iter)
            
            # Move to next line (including newline character)
            char_offset += len(line) + 1