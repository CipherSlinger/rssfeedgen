# PyQt5
# PyQtWebEngine

import sys
import re
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QDialog, QLabel, QTextBrowser, QScrollArea
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt5.QtCore import QUrl, Qt, QObject, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWebChannel import QWebChannel

# Create a JavaScript handler class
class JSHandler(QObject):
    htmlReceived = pyqtSignal(str)
    
    @pyqtSlot(str)
    def receiveHtml(self, html):
        """Slot to receive HTML from JavaScript"""
        print(f"HTML received in handler, length: {len(html)}")
        self.htmlReceived.emit(html)

    # Add debugging slots
    @pyqtSlot()
    def debug(self):
        print("Debug slot called")

    @pyqtSlot(str)
    def log(self, message):
        print(f"JS Log: {message}")

class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        level_names = {0: "DEBUG", 1: "INFO", 2: "WARNING", 3: "ERROR"}
        level_name = level_names.get(level, "UNKNOWN")
        source = sourceID.split('/')[-1] if sourceID else "unknown"
        print(f"JS {level_name}: {message} [line {lineNumber}] [{source}]")

class CompactBrowser(QWidget):
    def __init__(self, url):
        super().__init__()
        self.setup_ui()
        self.selected_container = None
        self.drag_pos = None
        
        # Create the JavaScript handler
        self.js_handler = JSHandler()
        self.js_handler.htmlReceived.connect(self.handle_selection)
        
        # Set up the page and profile
        self.profile = QWebEngineProfile("browser_profile")
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        
        # Create and set the page
        self.page = WebEnginePage(self.profile)
        self.webview.setPage(self.page)
        
        # Connect to page loading
        self.page.loadFinished.connect(self.on_load_finished)
        
        # Load the URL
        self.webview.load(QUrl(url))
    
    def setup_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(1280, 720)

        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(25, 25)
        close_btn.setFont(QFont("Arial", 12, QFont.Bold))
        close_btn.clicked.connect(self.close)

        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)

        self.webview = QWebEngineView()
        
        # Configure settings
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.webview)

        self.setStyleSheet("""
            QWidget { background: #f0f0f0; }
            QPushButton {
                background: #ff4444; 
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover { background: #ff6666; }
        """)
    
    def on_load_finished(self, success):
        if success:
            print("Page loaded successfully, setting up bridge...")
            
            # 确保WebView获得焦点，这样可以接收键盘事件
            self.webview.setFocus()
            # Add the JavaScript handler to the page
            self.page.runJavaScript("""
                // Create a global object to hold our Python bridge
                window.pyBridge = {
                    sendToPython: function(html) {
                        // This will be replaced with the actual bridge function
                        console.error("Python bridge not initialized yet");
                    }
                };
                
                console.log("Initial bridge placeholder created");
            """)
            
            # Add the handler to the page
            self.setup_js_python_bridge()
        else:
            print("Page failed to load")
    
    def setup_js_python_bridge(self):
        """Set up the proper bridge between JavaScript and Python"""
        
        # First inject qwebchannel.js content directly
        qwebchannel_js = """
        // qwebchannel.js minimal version - embedded directly
        var QWebChannelMessageTypes = {
            signal: 1,
            propertyUpdate: 2,
            init: 3,
            idle: 4,
            debug: 5,
            invokeMethod: 6,
            connectToSignal: 7,
            disconnectFromSignal: 8,
            setProperty: 9,
            response: 10,
        };

        var QWebChannel = function(transport, initCallback) {
            if (typeof transport !== "object" || typeof transport.send !== "function") {
                console.error("The QWebChannel expects a transport object with a send function and onmessage callback property.");
                return;
            }

            var channel = this;
            this.transport = transport;

            this.send = function(data) {
                if (typeof data !== "string") {
                    data = JSON.stringify(data);
                }
                channel.transport.send(data);
            };

            this.transport.onmessage = function(message) {
                var data = message.data;
                if (typeof data === "string") {
                    data = JSON.parse(data);
                }
                switch (data.type) {
                    case QWebChannelMessageTypes.signal:
                        channel.handleSignal(data);
                        break;
                    case QWebChannelMessageTypes.response:
                        channel.handleResponse(data);
                        break;
                    case QWebChannelMessageTypes.propertyUpdate:
                        channel.handlePropertyUpdate(data);
                        break;
                    default:
                        console.error("Invalid message received:", message.data);
                        break;
                }
            };

            this.execCallbacks = {};
            this.execId = 0;
            this.exec = function(data, callback) {
                if (!callback) {
                    channel.send(data);
                    return;
                }
                if (channel.execId === Number.MAX_VALUE) {
                    channel.execId = 0;
                }
                if (data.hasOwnProperty("id")) {
                    console.error("Cannot exec message with property id: " + JSON.stringify(data));
                    return;
                }
                data.id = channel.execId++;
                channel.execCallbacks[data.id] = callback;
                channel.send(data);
            };

            this.objects = {};

            this.handleSignal = function(message) {
                var object = channel.objects[message.object];
                if (object) {
                    object.signalEmitted(message.signal, message.args);
                } else {
                    console.warn("Unhandled signal: " + message.object + "::" + message.signal);
                }
            };

            this.handleResponse = function(message) {
                if (!message.hasOwnProperty("id")) {
                    console.error("Invalid response message received: ", JSON.stringify(message));
                    return;
                }
                channel.execCallbacks[message.id](message.data);
                delete channel.execCallbacks[message.id];
            };

            this.handlePropertyUpdate = function(message) {
                for (var i = 0; i < message.data.length; ++i) {
                    var data = message.data[i];
                    var object = channel.objects[data.object];
                    if (object) {
                        object.propertyUpdate(data.signals, data.properties);
                    } else {
                        console.warn("Unhandled property update: " + data.object + "::" + data.signal);
                    }
                }
                channel.exec({type: QWebChannelMessageTypes.idle});
            };

            this.debug = function(message) {
                channel.send({type: QWebChannelMessageTypes.debug, data: message});
            };

            channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
                for (var objectName in data) {
                    var object = new QObject(objectName, data[objectName], channel);
                }
                if (initCallback) {
                    initCallback(channel);
                }
                channel.exec({type: QWebChannelMessageTypes.idle});
            });
        };

        function QObject(name, data, webChannel) {
            this.__id__ = name;
            webChannel.objects[name] = this;

            this.propertyUpdate = function(signals, propertyMap) {
                for (var propertyIndex in propertyMap) {
                    var propertyValue = propertyMap[propertyIndex];
                    this[propertyIndex] = propertyValue;
                }
                for (var signalName in signals) {
                    var signalIndex = signals[signalName];
                    if (signalIndex) {
                        this[signalName + "Changed"].connect(function() {
                            webChannel.exec({
                                type: QWebChannelMessageTypes.propertyUpdate,
                                object: name,
                                signals: signals,
                                properties: ''
                            });
                        });
                    }
                }
            };

            this.signalEmitted = function(signalName, signalArgs) {
                var connections = this[signalName];
                if (connections) {
                    connections.forEach(function(callback) {
                        callback.apply(callback, signalArgs);
                    });
                }
            };

            for (var propertyIndex in data.properties) {
                this[propertyIndex] = data.properties[propertyIndex];
            }

            for (var methodIndex in data.methods) {
                var methodName = data.methods[methodIndex];
                this[methodName] = function() {
                    var args = [];
                    var callback;
                    for (var i = 0; i < arguments.length; ++i) {
                        if (typeof arguments[i] === "function")
                            callback = arguments[i];
                        else
                            args.push(arguments[i]);
                    }

                    webChannel.exec({
                        type: QWebChannelMessageTypes.invokeMethod,
                        object: name,
                        method: methodName,
                        args: args
                    }, function(response) {
                        if (callback) {
                            callback(response);
                        }
                    });
                };
            }

            for (var signalIndex in data.signals) {
                var signalName = data.signals[signalIndex];
                this[signalName] = new QSignal(this, signalName, webChannel);
            }
        }

        function QSignal(qObject, signalName, webChannel) {
            var connections = [];
            qObject[signalName] = connections;

            this.connect = function(callback) {
                connections.push(callback);
                webChannel.exec({
                    type: QWebChannelMessageTypes.connectToSignal,
                    object: qObject.__id__,
                    signal: signalName
                });
            };

            this.disconnect = function(callback) {
                var idx = connections.indexOf(callback);
                if (idx !== -1) {
                    connections.splice(idx, 1);
                }
                if (connections.length === 0) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: qObject.__id__,
                        signal: signalName
                    });
                }
            };
        }
        """
        
        # Inject the qwebchannel.js into the page
        self.page.runJavaScript(qwebchannel_js)
        
        # Register the handler
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("handler", self.js_handler)
        self.page.setWebChannel(self.channel)
        
        # Create a direct method to call invokeMethod instead of trying to call the method directly
        self.page.runJavaScript("""
            // Global channel reference
            var _pythonChannel = null;
            
            // Set up the bridge with invokeMethod approach
            function setupPythonBridge() {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    _pythonChannel = channel;
                    console.log("QWebChannel initialized with objects:", Object.keys(channel.objects));
                    
                    if (channel.objects.handler) {
                        console.log("Handler found with methods:", Object.keys(channel.objects.handler));
                        
                        // Set up the bridge function using invokeMethod approach
                        window.pyBridge.sendToPython = function(html) {
                            try {
                                console.log("Sending HTML to Python using invokeMethod, length:", html.length);
                                
                                // Use exec with a callback to send data to Python
                                channel.exec({
                                    type: QWebChannelMessageTypes.invokeMethod,
                                    object: "handler",
                                    method: "receiveHtml",
                                    args: [html]
                                }, function(response) {
                                    console.log("HTML sent successfully, response:", response);
                                });
                            } catch(e) {
                                console.error("Error sending to Python:", e);
                            }
                        };
                        
                        // Test function that always uses a callback
                        window.testPythonBridge = function() {
                            try {
                                channel.exec({
                                    type: QWebChannelMessageTypes.invokeMethod,
                                    object: "handler",
                                    method: "debug",
                                    args: []
                                }, function(response) {
                                    console.log("Debug method called with callback, response:", response);
                                });
                            } catch(e) {
                                console.error("Error calling debug:", e);
                            }
                        };
                        
                        // Test it after a delay
                        setTimeout(window.testPythonBridge, 1000);
                        
                        console.log("Python bridge registered with improved approach");
                    } else {
                        console.error("Handler not found in channel");
                    }
                });
            }
            
            // Run the setup function
            setupPythonBridge();
        """, lambda result: self.setup_detection_script())
    
    def setup_detection_script(self):
        """Set up all detection and selection scripts"""
        print("Setting up detection scripts...")
        
        # 1. Add styles for highlighting
        self.page.runJavaScript("""
            document.head.insertAdjacentHTML('beforeend', `
                <style>
                    .auto-highlight {
                        border: 3px solid #ff0000 !important;
                        box-shadow: 0 0 15px rgba(255,0,0,0.5) !important;
                    }
                    .selection-status {
                        position: fixed;
                        top: 10px;
                        right: 10px;
                        background: #2ecc71;
                        color: white;
                        padding: 8px 12px;
                        border-radius: 4px;
                        z-index: 9999;
                        font-family: Arial, sans-serif;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                        display: none;
                    }
                </style>
            `);
            
            // Add status indicator
            const statusIndicator = document.createElement('div');
            statusIndicator.className = 'selection-status';
            statusIndicator.textContent = 'Selection Ready - Press Enter';
            document.body.appendChild(statusIndicator);
            
            console.log("Styles and status indicator added");
        """)
        
        # 2. Add detection logic
        date_regex = re.compile(
            r"(\d{4}[-\/年]\d{1,2}[-\/月]\d{1,2})|"
            r"(\d{1,2}[-\/月]\d{1,2}[-\/日]\d{4})"
        ).pattern.replace("\\", "\\\\")
        
        self.page.runJavaScript(f"""
            const DATE_REGEX = new RegExp("{date_regex}");
            window.lastHighlighted = null;
            window.selectedContainer = null;

            function findListContainer(element) {{
                let current = element;
                while (current) {{
                    if (isListContainer(current)) return current;
                    current = current.parentElement;
                }}
                return null;
            }}

            function isListContainer(el) {{
                if (/(list|container|wrap)/i.test(el.id)) return true;
                const listClasses = ['list', 'news-list', 'items', 'kjj_list'];
                if (listClasses.some(c => el.classList.contains(c))) return true;
                const children = el.children;
                if (children.length < 3) return false;
                let validCount = 0;
                for (let i = 0; i < Math.min(3, children.length); i++) {{
                    const item = children[i];
                    if (item.querySelector('a') && DATE_REGEX.test(item.textContent)) {{
                        validCount++;
                    }}
                }}
                return validCount >= 2;
            }}

            document.addEventListener('mousemove', e => {{
                const hovered = document.elementFromPoint(e.clientX, e.clientY);
                const container = findListContainer(hovered);
                if (container && container !== window.lastHighlighted) {{
                    if (window.lastHighlighted) {{
                        window.lastHighlighted.classList.remove('auto-highlight');
                    }}
                    container.classList.add('auto-highlight');
                    window.lastHighlighted = container;
                    window.selectedContainer = container;
                    
                    // Show status indicator
                    document.querySelector('.selection-status').style.display = 'block';
                }}
            }});
            
            console.log("Detection logic initialized");
        """)
        
        # 3. Add Enter key handler with direct bridge
        self.page.runJavaScript("""
            // Remove any existing handler
            if (window._keyHandler) {
                document.removeEventListener('keydown', window._keyHandler);
            }
            
            // Create new handler
            window._keyHandler = function(e) {
                if (e.key === 'Enter' && window.selectedContainer) {
                    console.log("Enter pressed with selection");
                    
                    // Show processing status
                    const status = document.querySelector('.selection-status');
                    status.textContent = 'Processing...';
                    status.style.background = '#3498db';
                    
                    try {
                        const html = window.selectedContainer.outerHTML;
                        console.log(`Sending HTML to Python, length: ${html.length}`);
                        
                        // Send to Python using our bridge function
                        if (window.pyBridge && window.pyBridge.sendToPython) {
                            window.pyBridge.sendToPython(html);
                            
                            // Show success status
                            status.textContent = 'Selection Processed ✓';
                            status.style.background = '#2ecc71';
                            setTimeout(() => {
                                status.style.display = 'none';
                            }, 2000);
                        } else {
                            console.error("Python bridge not available");
                            status.textContent = 'Error: Bridge not available';
                            status.style.background = '#e74c3c';
                        }
                    } catch (e) {
                        console.error("Error sending to Python:", e);
                        status.textContent = 'Error: ' + e.message;
                        status.style.background = '#e74c3c';
                    }
                }
            };
            
            // Add the handler
            document.addEventListener('keydown', window._keyHandler);
            console.log("Enter key handler attached");
            
            // Test the bridge
            setTimeout(function() {
                if (window.pyBridge && window.pyBridge.sendToPython) {
                    console.log("Bridge is ready");
                } else {
                    console.error("Bridge not ready after timeout");
                }
            }, 1000);
        """)
        # 最后添加这一行，确保设置完所有脚本后WebView获得焦点
        self.webview.setFocus()
    
    def handle_selection(self, html):
        if not html:
            print("错误: 接收到空HTML内容")
            return

        self.selected_container = html
        
        # 定义日期正则表达式
        date_regex = re.compile(
            r"(\d{4}[-\/年]\d{1,2}[-\/月]\d{1,2})|"
            r"(\d{1,2}[-\/月]\d{1,2}[-\/日]\d{4})"
        ).pattern.replace("\\", "\\\\")
        
        # 直接在当前页面上实现选择器分析，而不是使用临时 div
        self.page.runJavaScript(f"""
            (function() {{
                // 直接分析页面上的元素
                const container = document.querySelector('.auto-highlight');
                if (!container) {{
                    console.log("No highlighted container found");
                    return null;
                }}

                // 定义日期正则表达式
                const DATE_REGEX = new RegExp("{date_regex}");
                console.log("Container found:", container.tagName, container.className);
                
                function getContainerSelector(el) {{
                    if (!el) return "body";
                    
                    // 尝试生成一个绝对路径选择器
                    let path = '';
                    let current = el;
                    const maxPathLength = 6; // 限制路径长度，避免过长
                    let pathCount = 0;
                    
                    while (current && current !== document.body && pathCount < maxPathLength) {{
                        let currentSelector = '';
                        
                        // 如果元素有ID，优先使用ID
                        if (current.id && !/\\d/.test(current.id)) {{
                            currentSelector = `#${{current.id}}`;
                            path = currentSelector + (path ? ' > ' + path : '');
                            break; // ID是唯一的，可以直接中断
                        }}
                        
                        // 否则使用标签名和类名
                        currentSelector = current.tagName.toLowerCase();
                        
                        // 添加类名，但排除动态类和高亮类
                        const classes = Array.from(current.classList || []).filter(c => 
                            !c.startsWith('js-') && 
                            c !== 'auto-highlight' && 
                            !c.includes('active') &&
                            !c.includes('hover')
                        );
                        
                        if (classes.length > 0) {{
                            currentSelector += '.' + classes.join('.');
                        }}
                        
                        // 如果当前元素有同级元素，尝试添加nth-child
                        const parent = current.parentElement;
                        if (parent) {{
                            const siblings = Array.from(parent.children);
                            if (siblings.length > 1) {{
                                const index = siblings.indexOf(current) + 1;
                                currentSelector += `:nth-child(${{index}})`;
                            }}
                        }}
                        
                        // 构建路径
                        path = currentSelector + (path ? ' > ' + path : '');
                        current = current.parentElement;
                        pathCount++;
                    }}
                    
                    console.log("Generated container path:", path);
                    return path || el.tagName.toLowerCase();
                }}

                function getBestSelector(elements) {{
                    if (!elements || elements.length === 0) return 'tr';
                    const tagNames = elements.map(el => el.tagName.toLowerCase());
                    if (new Set(tagNames).size === 1) return tagNames[0];
                    const sampleClasses = Array.from(elements[0].classList || []).filter(c => c !== 'auto-highlight');
                    const commonClasses = sampleClasses.filter(c => elements.every(el => el.classList.contains(c)));
                    if (commonClasses.length > 0) {{
                        return `${{elements[0].tagName.toLowerCase()}}.${{commonClasses.join('.')}}`;
                    }}
                    return `${{container.tagName.toLowerCase()}} > ${{elements[0].tagName.toLowerCase()}}`;
                }}

                function getRelativePath(element, container) {{
                    if (!element) return 'a'; // 默认返回
                    if (element === container) return '';
                    let path = element.tagName.toLowerCase();
                    if (element.className) {{
                        const classes = element.className.split(' ').filter(c => c && !c.includes('active') && !c.includes('current')).map(c => '.' + c);
                        if (classes.length) path += classes.join('');
                    }}
                    if (element.id && !/\\d/.test(element.id)) {{
                        path = '#' + element.id;
                    }}
                    
                    // 针对常见元素的特殊处理
                    if (element.tagName === 'A') return 'a';
                    if (element.tagName === 'SPAN' && element.className && element.className.includes('time')) return 'span.time';
                    if (element.tagName === 'TD' && element.cellIndex === 1) return 'td:nth-child(2)';
                    
                    return path;
                }}

                // 查找列表项
                let items = [];
                if (container.tagName === 'TBODY') {{
                    items = Array.from(container.querySelectorAll('tr'));
                }} else {{
                    items = Array.from(container.children || []);
                }}
                
                // 过滤出有链接和日期的项
                items = items.filter(el => {{
                    return el.querySelector('a') && DATE_REGEX.test(el.textContent);
                }});
                
                console.log("Found " + items.length + " items in container");
                
                if (items.length === 0) {{
                    // 尝试额外的检测方式
                    items = Array.from(container.querySelectorAll('*')).filter(el => 
                        el.querySelector('a') && DATE_REGEX.test(el.textContent) && 
                        (el.tagName === 'LI' || el.tagName === 'TR' || el.tagName === 'DIV')
                    );
                    console.log("Secondary detection found " + items.length + " items");
                }}
                
                // 如果还是没找到，使用所有带链接的元素
                if (items.length === 0) {{
                    items = Array.from(container.querySelectorAll('a')).map(a => a.parentElement);
                    console.log("Fallback to all links, found " + items.length + " potential items");
                }}
                
                const sampleItem = items[0];
                let linkElement = null;
                let dateElement = null;
                
                if (sampleItem) {{
                    linkElement = sampleItem.querySelector('a');
                    
                    // 查找日期元素
                    // 1. 尝试在直接子节点中查找
                    dateElement = Array.from(sampleItem.childNodes || []).find(n => 
                        n.textContent && DATE_REGEX.test(n.textContent)
                    );
                    
                    // 2. 如果没找到，尝试在所有后代元素中查找
                    if (!dateElement) {{
                        const allElements = sampleItem.querySelectorAll('*');
                        for (const el of allElements) {{
                            if (el.textContent && DATE_REGEX.test(el.textContent)) {{
                                dateElement = el;
                                break;
                            }}
                        }}
                    }}
                    
                    // 3. 如果还没找到，查找所有包含数字的元素
                    if (!dateElement) {{
                        const numericElements = Array.from(sampleItem.querySelectorAll('*')).filter(
                            el => /\\d/.test(el.textContent)
                        );
                        if (numericElements.length > 0) {{
                            dateElement = numericElements[0];
                        }}
                    }}
                }}

                // 创建选择器对象
                let itemSelector = getBestSelector(items);
                if (items.length === 0) {{
                    itemSelector = container.tagName.toLowerCase() === 'table' ? 'tr' : 
                                  (container.tagName.toLowerCase() === 'ul' ? 'li' : 'div');
                }}
                
                const result = {{
                    container: getContainerSelector(container),
                    item: itemSelector,
                    title: linkElement ? getRelativePath(linkElement, container) : 'a',
                    date: dateElement ? getRelativePath(dateElement, container) : 'td:nth-child(2)',
                    link: linkElement ? getRelativePath(linkElement, container) : 'a'
                }};
                
                console.log("Selectors generated:", JSON.stringify(result));
                return result;
            }})();
        """, self.extract_data)

    def extract_data(self, selectors):
        if not selectors:
            QMessageBox.warning(self, "错误", "未找到有效列表容器")
            return

        print(f"使用选择器: {selectors}")
        
        item_selector_base = selectors["item"].split('.')[0] if '.' in selectors["item"] else selectors["item"]
        
        js_code = f"""
            (function() {{
                try {{
                    // 首先获取容器
                    const container = document.querySelector('{selectors["container"]}');
                    if (!container) {{
                        console.error("找不到容器:", '{selectors["container"]}');
                        return [];
                    }}
                    
                    console.log("找到容器:", container.tagName, container.className); //, container.outerHTML
                    
                    // 使用相对于容器的选择器查找项目
                    let items;
                    if ('{selectors["item"]}'.includes('>')) {{
                        // 如果是复合选择器，使用全局查询
                        items = Array.from(document.querySelectorAll('{selectors["item"]}'));
                    }} else {{
                        // 否则在容器内查询子元素
                        items = Array.from(container.querySelectorAll('{selectors["item"]}'));
                        
                        // 如果容器内找不到元素，尝试直接使用子元素
                        if (items.length === 0) {{
                            items = Array.from(container.children).filter(el => 
                                el.tagName.toLowerCase() === '{item_selector_base}'
                            );
                        }}
                    }}
                    
                    console.log("找到 {selectors['item']} 元素:", items.length);
                    
                    // 如果没有找到任何项，尝试通用备用方案
                    if (items.length === 0) {{
                        if (container.tagName === 'TABLE' || container.tagName === 'TBODY') {{
                            items = Array.from(container.querySelectorAll('tr'));
                        }} else if (container.tagName === 'UL' || container.tagName === 'OL') {{
                            items = Array.from(container.querySelectorAll('li'));
                        }} else {{
                            items = Array.from(container.children);
                        }}
                        console.log("备用方法找到元素:", items.length);
                    }}
                    
                    // 最后尝试：获取所有带链接的元素
                    if (items.length === 0) {{
                        items = Array.from(container.querySelectorAll('a')).map(a => a.parentElement || a);
                        items = [...new Set(items)]; // 去重
                        console.log("链接元素备用方案找到:", items.length);
                    }}
                    
                    if (items.length === 0) {{
                        console.log("无法找到列表项，请检查选择器");
                        return [];
                    }}
                    
                    const results = items.map(item => {{
                        // 尝试在当前项内查找元素
                        const titleEl = item.querySelector('{selectors["title"]}') || item.querySelector('a') || item;
                        const linkEl = item.querySelector('{selectors["link"]}') || item.querySelector('a');
                        
                        // 日期可能在文本节点中，需要特殊处理
                        let dateEl = item.querySelector('{selectors["date"]}');
                        if (!dateEl) {{
                            // 尝试查找包含日期格式的元素
                            dateEl = Array.from(item.querySelectorAll('*')).find(el => 
                                /\\d{{4}}[-\\/年]\\d{{1,2}}/.test(el.innerText)
                            );
                        }}
                        
                        // 如果仍然找不到日期，检查项目本身的文本
                        let dateText = dateEl ? dateEl.innerText : '';
                        if (!dateText) {{
                            const dateMatch = item.innerText.match(/(\\d{{4}}[-\\/年]\\d{{1,2}}[-\\/月]\\d{{1,2}}|\\d{{1,2}}[-\\/月]\\d{{1,2}}[-\\/日]\\d{{4}})/);
                            if (dateMatch) dateText = dateMatch[0];
                        }}
                        
                        return {{
                            "title": titleEl?.innerText?.trim() || '',
                            "link": linkEl?.href || '',
                            "date": dateText?.trim() || ''
                        }};
                    }}).filter(item => item.title && (item.link || item.date));
                    
                    console.log("提取了 " + results.length + " 个项目");
                    return results;
                }} catch(e) {{
                    console.error("提取数据时出错:", e);
                    return [];
                }}
            }})();
        """

        self.page.runJavaScript(js_code, self.show_results_dialog)

    def show_results_dialog(self, results):
        """显示提取结果的对话框"""
        if not results or len(results) == 0:
            QMessageBox.information(self, "提示", "未提取到任何结果")
            return
        
        # 创建并显示结果对话框
        dialog = ResultDialog(results, self)
        dialog.exec_()

    def mousePressEvent(self, event):
        if event.y() < 30:
            self.drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.drag_pos:
            delta = event.globalPos() - self.drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

# 添加这个自定义结果对话框类
class ResultDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results
        self.setWindowTitle("Extract Results")
        self.setMinimumSize(600, 400)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 显示结果计数
        count_label = QLabel(f"Found {len(self.results)} results")
        count_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(count_label)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # 为每个结果创建展示区域
        for i, item in enumerate(self.results):
            title = item.get('title', '')
            link = item.get('link', '')
            date = item.get('date', '')
            
            # 创建一个框架来包含每个结果 - 只在底部添加边框作为分割线
            result_frame = QWidget()
            result_frame.setStyleSheet("border-bottom: 1px solid #cccccc; margin-bottom: 8px;")
            result_layout = QVBoxLayout(result_frame)
            result_layout.setSpacing(2)  # 减小内部字段之间的间距
            result_layout.setContentsMargins(5, 5, 5, 10)
            
            # 标题
            title_label = QLabel(f"<b>Title:</b> {title}")
            title_label.setWordWrap(True)
            title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            result_layout.addWidget(title_label)
            
            # 链接
            link_label = QLabel(f"<b>Link:</b> <a href='{link}'>{link}</a>")
            link_label.setOpenExternalLinks(True)
            link_label.setWordWrap(True)
            result_layout.addWidget(link_label)
            
            # 日期
            date_label = QLabel(f"<b>Date:</b> {date}")
            result_layout.addWidget(date_label)
            
            content_layout.addWidget(result_frame)
        
        # 添加一些底部填充
        content_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # 创建水平布局来放置按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        save_btn = QPushButton("Save")
        # save_btn.clicked.connect(self.save_results)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        # 添加按钮到水平布局
        button_layout.addWidget(save_btn)
        button_layout.addWidget(close_btn)
        
        # 将按钮布局添加到主布局
        layout.addLayout(button_layout)
        
        # 调整窗口大小以适应内容
        self.adjustSize()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    browser = CompactBrowser(url="https://kjj.gz.gov.cn/xxgk/zcfg/index.html")
    browser.show()
    sys.exit(app.exec_())

    # https://kjj.gz.gov.cn/xxgk/zcfg/
    # https://gdstc.gd.gov.cn/zwgk_n/tzgg/
    # https://www.hp.gov.cn/gzhpkj/gkmlpt/index