from gi.repository import GObject, Gedit, Gtk, GLib

#from llm_utils import load_model
import threading
import requests
import subprocess
import re
import os
import time


import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "myplugin"
CONFIG_FILE = CONFIG_DIR / "config.ini"

config = configparser.ConfigParser()

models_dir = None

if CONFIG_FILE.exists():
    config.read(CONFIG_FILE)
    models_dir = config.get("models", "path", fallback=None)

if models_dir:
    models_dir = Path(models_dir).expanduser()
else:
    # fallback to default
    models_dir = Path(__file__).resolve().parent / "models" 






class TextFlowPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "TextFlowPlugin"
    window = GObject.Property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._handlers = {}
        self._tags_created = set()
        self._llm = None
        self.llm_names = []
        self.this_dir = os.path.dirname(__file__)
        self.models_dir = models_dir

        print('This dir')
        print(self.this_dir)


        self.time_check = time.time()

    ## On start

    def do_activate(self):
        print("TextFlow activated!")
        
        self.load_llm_async()

        self._handlers['tab-added'] = self.window.connect('tab-added', self.on_tab_added)
        
        for doc in self.window.get_documents():
            self.connect_document(doc)



    ## on close

    def do_deactivate(self):
        print("TextFlow deactivated!")

        print(os.getcwd())
        
        # Stop LLM server on deactivation
        self.stop_llm_server()
        
        for handler_id in self._handlers.values():
            self.window.disconnect(handler_id)
        self._handlers.clear()



    ## Getting the words

    def connect_document(self, doc):
        # Remove the server start from here
        doc.connect('changed', self.on_document_changed)
        self.setup_tags(doc)
        
        # Extract names on first connect
        start = doc.get_start_iter()
        end = doc.get_end_iter()
        text = doc.get_text(start, end, False)
        
        if text.strip():  # Only if there's content
            names = self.extract_names_async(text)
            print(f"Extracted names: {names}")
            # TODO: Store names and assign colors
        
        print(f"Connected to document")

    def do_update_state(self):
        pass

    def on_tab_added(self, window, tab):
        doc = tab.get_document()
        self.connect_document(doc)


    def extract_names_from_text(self, text):
        names = []
        try:
            names = self._extract_names_from_text(text)
        finally:
            self.stop_llm_server()
        print('names extracted:')
        print(names)
        return names

    def _extract_names_from_text(self, text):
        """Call the LLM server to extract names from text"""
        if not hasattr(self, 'llm_server_url'):
            print("LLM server URL not set. Did you call load_llm_model?")
            return []
        try:
            resp = requests.post(
                f"{self.llm_server_url}/extract_names",
                json={"text": text}
            )
            if resp.status_code == 200:
                print(resp.json())
                data = resp.json()
                return data.get('names', [])
            else:
                print(f"LLM server error: {resp.text}")
                return []
        except Exception as e:
            print(f"Failed to contact LLM server: {e}")
            return []
        

    #### Tagging the words & colouring them in

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

        # Create a tag for completed items (containing "tick, but" or "Tick, but")
        if not tag_table.lookup('completed-item-but'):
            tag = doc.create_tag('completed-item-but', foreground="#98c03a")  # Green
            print("Created completed-item-but tag")

        # Create a tag for completed items (containing "tick, but" or "Tick, but")
        if not tag_table.lookup('maybe-completed-item'):
            tag = doc.create_tag('maybe-completed-item', foreground="#c09c3a")  # Green
            print("Created maybe-completed-item tag")

        self._tags_created.add(doc_id)


    def add_dynamic_tags(self, doc):
        """Apply pastel color tags to names in self.llm_names"""
        if not self.llm_names or not isinstance(self.llm_names, list):
            return
        tag_table = doc.get_tag_table()
        # Define a pastel color mapping for common color names
        pastel_colors = {
            'red': '#ffb3ba',
            'yellow': '#fff6b3',
            'green': '#baffc9',
            'blue': "#8ac4f0",
            'purple': '#e0bbff',
            'orange': '#ffd6a5',
            'pink': '#ffb7ce',
            'grey': '#e2e2e2',
            'black': "#070606FF",
            'brown': '#e4c1b9',
            'teal': '#b3fff6',
            'default': '#e0e0e0',
        }
        for pair in self.llm_names:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            name, color = pair
            tag_name = f"llm-name-{color}"
            pastel = pastel_colors.get(str(color).lower(), pastel_colors['default'])
            if not tag_table.lookup(tag_name):
                doc.create_tag(tag_name, foreground=pastel)
        # Apply tags to all occurrences of each name
        start = doc.get_start_iter()
        end = doc.get_end_iter()
        text = doc.get_text(start, end, False)
        for pair in self.llm_names:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            name, color = pair
            tag_name = f"llm-name-{color}"
            for match in re.finditer(re.escape(name), text, re.IGNORECASE):
                s, e = match.start(), match.end()
                start_iter = doc.get_iter_at_offset(s)
                end_iter = doc.get_iter_at_offset(e)
                doc.apply_tag_by_name(tag_name, start_iter, end_iter)

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


        # throttle name extraction to once every 10 seconds
        now = time.time()
        if now - self.time_check < 2:
            self.time_check = now
            # not enough time elapsed since last extraction; skip
            #print(f"Skipping name extraction; last run {now - self.time_check:.1f}s ago")
            return
        # update last-run timestamp and allow extraction to proceed
        self.time_check = now
        self.llm_names = self._extract_names_from_text(text)
        print('names extracted:')
        print(self.llm_names)

        self.add_dynamic_tags(doc)

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

                if 'tick, but' in line.lower():
                    doc.apply_tag_by_name('completed-item-but', start_iter, end_iter)
                elif 'tick' in line.lower():
                    doc.apply_tag_by_name('completed-item', start_iter, end_iter)
                elif 'maybe' in line.lower():
                    doc.apply_tag_by_name('maybe-completed-item', start_iter, end_iter)
                else:
                    doc.apply_tag_by_name('task-item', start_iter, end_iter)


                ## LLM stuff

                if 'I see you' in line.lower():
                    self.run_inference_async("I see you")
            
            # Move to next line (including newline character)
            char_offset += len(line) + 1
        # After all other highlighting, apply dynamic tags for names
        self.add_dynamic_tags(doc)




### Async Stuff

        
    def load_the_model(self):
        # ❌ NO GTK CALLS HERE
        self.start_llm_server()
        print("Waiting for LLM server to be ready...")
        
        # Wait for server to be ready
        
        for i in range(10):
            try:
                resp = requests.get('http://localhost:19953/health', timeout=1)
                if resp.status_code == 200:
                    print("LLM server is ready to load a model - response:", resp.json())
                    break
            except:
                pass
            time.sleep(1)
        
        # Now load model
        self.load_llm_model()
        result = "done"

        # Schedule UI update safely
        GLib.idle_add(self.on_work_finished, result)

    def on_work_finished(self, result):
        # ✅ Safe to touch GTK here
        print("Model Loading finished: ", result)
        return False  # important: remove idle handler

    def load_llm_async(self):
        thread = threading.Thread(target=self.load_the_model, daemon=True)
        thread.start()

    def do_inference_work(self, prompt, max_tokens=150, temperature=0.3, stop=None):
        # ❌ NO GTK CALLS HERE
        if stop is None:
            stop = ["</s>", "\n\n"]
        print("Waiting for LLM server to be ready for inference...")
        import time
        for i in range(10):
            try:
                resp = requests.get('http://localhost:19953/health', timeout=1)
                if resp.status_code == 200 and resp.json().get('model_loaded'):
                    print("LLM server is ready for inference - response:", resp.json())
                    break
            except Exception as e:
                print(f"Health check failed (attempt {i+1}/10): {e}")
            time.sleep(1)
        else:
            print("LLM server not ready for inference after multiple attempts.")
            GLib.idle_add(self.on_inference_finished, None)
            return

        # Now do inference
        try:
            headers = {'Content-Type': 'application/json'}
            payload = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stop": stop
            }
            resp = requests.post(
                f"http://localhost:19953/inference",
                json=payload,
                headers=headers,
                timeout=30
            )
            if resp.status_code == 200:
                result = resp.json().get('response', '')
                print(f"Inference result: {result}")
            else:
                print(f"LLM server inference error: {resp.text}")
                result = None
        except Exception as e:
            print(f"Failed to contact LLM server for inference: {e}")
            result = None

        # Schedule UI update safely
        GLib.idle_add(self.on_inference_finished, result)

    def on_inference_finished(self, result):
        # ✅ Safe to touch GTK here
        print("Inference finished:", result)
        # You can update the UI or handle the result here
        return False  # important: remove idle handler

    def run_inference_async(self, prompt, max_tokens=150, temperature=0.3, stop=None):
        thread = threading.Thread(target=self.do_inference_work, args=(prompt, max_tokens, temperature, stop), daemon=True)
        thread.start()

    def do_extract_names_work(self, text, prompts_path=None):
        """Background thread: call LLM server to extract names."""
        if not hasattr(self, 'llm_server_url'):
            print("LLM server URL not set. Did you call load_llm_model?")
            result = []
        else:
            try:
                payload = {"text": text}
                if prompts_path:
                    payload["prompts_path"] = prompts_path
                resp = requests.post(
                    f"{self.llm_server_url}/extract_names",
                    json=payload,
                    timeout=30
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get('names', [])
                else:
                    print(f"LLM server error: {resp.text}")
                    result = []
            except Exception as e:
                print(f"Failed to contact LLM server: {e}")
                result = []
        GLib.idle_add(self.on_extract_names_finished, result)

    def on_extract_names_finished(self, names):
        """Safe to touch GTK here. Update UI or state with extracted names."""
        print("Extracted names (async):", names)
        self.llm_names = names
        # Optionally, update tags in the current document here
        # Example: self.add_dynamic_tags(current_doc)
        return False  # Remove idle handler

    def extract_names_async(self, text, prompts_path=None):
        """Start async extraction of names from text."""
        thread = threading.Thread(target=self.do_extract_names_work, args=(text, prompts_path), daemon=True)
        thread.start()




#### LLM stuff



    def start_llm_server(self):
        """Start the LLM server using the env_and_load.sh script"""
        print('\n CWD: \n')
        print(os.getcwd())
        script_path = os.path.join(os.path.dirname(__file__), 'env_and_load.sh')
        log_path = os.path.join(os.path.dirname(__file__), 'logs', 'env_and_load.log')
        print(f"Running script at: {script_path}")
        try:
            print("Starting LLM server via env_and_load.sh...")
            with open(log_path, 'a') as log_file:
                subprocess.Popen(['bash', script_path], stdout=log_file, stderr=log_file)
            print(f"LLM server started via env_and_load.sh, output redirected to {log_path}")
        except Exception as e:
            print(f"Failed to start LLM server: {e}")

    def stop_llm_server(self):
        """Stop the LLM server using the PID file"""
        pid_file = self.this_dir + '/logs/llm_server.pid'
        
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
            try:
                os.kill(int(pid), 9)
                print(f"LLM server (PID {pid}) killed.")
            except Exception as e:
                print(f"Failed to kill LLM server: {e}")
            os.remove(pid_file)
        else:
            print("No llm_server.pid file found.")
            

    def load_llm_model(self):
        """Request the LLM server to load the model"""
        import time
        import json as _json

        server_url = 'http://localhost:19953'
        model_path = os.path.join(self.models_dir, 'pydevmini_full.gguf')  # Update if needed

        headers = {'Content-Type': 'application/json'}
        # Retry loop to ensure server is ready
        for i in range(10):
            try:
                resp = requests.post(
                    f"{server_url}/load_model",
                    data=_json.dumps({"model_path": model_path}),
                    headers=headers,
                    timeout=10
                )

                print(resp.json())
                if resp.status_code == 200:
                    print(f"\n LLM model loaded from {model_path} - response: {resp.json()} \n")
                    break
                else:
                    print(f"LLM server load_model error: {resp.text}")
            except Exception as e:
                print(f"Failed to contact LLM server (attempt {i+1}/10): {e}")
            time.sleep(1)
        else:
            print("Failed to load model after multiple attempts.")

        self.llm_server_url = server_url
        self.llm_model_path = model_path