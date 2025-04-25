# PyQt5
# PyQtWebEngine

import sys
import re
try:
    import yaml
except ImportError:
    print("PyYAML package is required. Please install it with 'pip install pyyaml'")
    yaml = None

from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QDialog, QLabel, QTextBrowser, QScrollArea, QDesktopWidget, QFormLayout, QLineEdit, QToolButton
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt5.QtCore import QUrl, Qt, QObject, pyqtSignal, pyqtSlot, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QPen, QPainterPath
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
        self.results = []
        self.current_selectors = {
            "container": "",
            "item": "",
            "title": "",
            "date": "",
            "link": ""
        }
        
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
        screen = QDesktopWidget().screenGeometry()  # Fetch screen size
        self.setFixedSize(int(screen.width() * 0.618), int(screen.height() * 0.618))

        # 设置全局应用样式
        self.setStyleSheet("""
            QWidget { 
                background-color: #f0f0f0; 
            }
            QLabel { 
                background-color: transparent; 
                border: none;
                padding: 0px;
                margin: 0px;
            }
            QPushButton {
                background-color: #ff4444; 
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover { 
                background-color: #ff6666; 
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            /* 滚动条样式 */
            QScrollBar:vertical {
                background-color: #ffffff;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #cdcdcd;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #808080;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            /* 水平滚动条样式 */
            QScrollBar:horizontal {
                background-color: #ffffff;
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cdcdcd;
                min-width: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::handle:horizontal:pressed {
                background-color: #808080;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            /* 结果区域边框样式 */
            #results_border_container {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)

        # Create new tab-style title bar
        self.title_bar = TabStyleTitleBar("广州开发区科学技术局")
        self.title_bar.close_btn.clicked.connect(self.close)

        # Create main horizontal layout
        main_content = QWidget()
        h_layout = QHBoxLayout(main_content)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)  # 确保没有间距

        # Create webview
        self.webview = QWebEngineView()
        
        # Configure settings
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        # Create a container for webview and status bar
        webview_container = QWidget()
        webview_container.setStyleSheet("background-color: #f0f0f0;")
        webview_layout = QVBoxLayout(webview_container)
        webview_layout.setContentsMargins(0, 0, 0, 0)
        webview_layout.setSpacing(0)
        
        # Status bar at the top of webview
        self.status_bar = QWidget()
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet("background-color: #e8f4fc; border-bottom: 1px solid #bbd5e8;")
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        
        # Status message
        self.status_message = QLabel("Hover over a list container and press Enter to extract data")
        self.status_message.setStyleSheet("color: #2980b9; font-weight: bold; background-color: transparent; border: none; padding: 0px;")
        status_layout.addWidget(self.status_message)
        
        # Add status bar and webview to container
        webview_layout.addWidget(self.status_bar)
        webview_layout.addWidget(self.webview)
        
        # Create results panel (initially hidden)
        self.results_panel = QWidget()
        self.results_panel.setMinimumWidth(320)
        self.results_panel.setMaximumWidth(500)
        self.results_panel.setVisible(False)
        self.results_panel.setObjectName("results_panel")
        
        # Set up the results panel
        self.results_layout = QVBoxLayout(self.results_panel)
        self.results_layout.setContentsMargins(0, 8, 8, 8)  # 移除左边距
        self.results_layout.setSpacing(8)
        
        # Set global styles for the results panel
        self.results_panel.setObjectName("results_panel")
        self.results_panel.setStyleSheet("background-color: #ffffff;")  # 移除左边框
        
        # Results panel header
        results_header = QWidget()
        results_header.setFixedHeight(40)
        results_header.setStyleSheet("background-color: #4a86e8; border-radius: 5px 5px 0 0; border-bottom: none;")
        header_layout = QHBoxLayout(results_header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        # Results icon
        results_icon = QLabel("📊")
        results_icon.setStyleSheet("font-size: 18px; color: white; background-color: transparent;")
        header_layout.addWidget(results_icon)
        
        # Results count label with white text
        self.count_label = QLabel("Results")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 18px; color: white; background-color: transparent;")
        header_layout.addWidget(self.count_label)
        
        header_layout.addStretch()
        
        # Add header to results layout
        self.results_layout.addWidget(results_header)
        
        # Create selectors editor section
        selector_section = QWidget()
        selector_section.setObjectName("selector_section")
        selector_layout = QVBoxLayout(selector_section)
        selector_layout.setSpacing(10)
        
        # Add styles - 更新样式
        selector_section.setStyleSheet("""
            background-color: #f8f8f8; 
            border: 1px solid #ddd; 
            border-top: none;
            border-radius: 0 0 8px 8px; 
            margin-bottom: 15px;
            padding: 5px;
        """)
        
        # Title for selectors section
        selector_header = QWidget()
        selector_header.setStyleSheet("background-color: #f8f8f8;")
        selector_header_layout = QHBoxLayout(selector_header)
        selector_header_layout.setContentsMargins(5, 0, 5, 0)
        
        selector_title = QLabel("CSS Selectors")
        selector_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 16px; background-color: transparent;")
        selector_header_layout.addWidget(selector_title)
        
        selector_subtitle = QLabel("(Edit to refine extraction)")
        selector_subtitle.setStyleSheet("color: #7f8c8d; font-size: 16px; background-color: transparent;")
        selector_header_layout.addWidget(selector_subtitle)
        selector_header_layout.addStretch()
        
        selector_layout.addWidget(selector_header)
        
        # Create form layout for selectors
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(8)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Create styled input fields for selectors
        self.container_input = QLineEdit()
        self.item_input = QLineEdit()
        self.title_input = QLineEdit()
        self.date_input = QLineEdit()
        self.link_input = QLineEdit()
        
        # Style all inputs - 简化样式表
        selector_input_style = "border: 1px solid #ccc; border-radius: 4px; padding: 7px; background-color: white; font-family: monospace; font-size: 16px;"
        self.container_input.setStyleSheet(selector_input_style)
        self.item_input.setStyleSheet(selector_input_style)
        self.title_input.setStyleSheet(selector_input_style)
        self.date_input.setStyleSheet(selector_input_style)
        self.link_input.setStyleSheet(selector_input_style)
        
        # Style labels
        label_style = "color: #34495e; font-weight: bold; font-size: 16px; background-color: transparent;"
        container_label = QLabel("Container:")
        container_label.setStyleSheet(label_style)
        item_label = QLabel("Item:")
        item_label.setStyleSheet(label_style)
        title_label = QLabel("Title:")
        title_label.setStyleSheet(label_style)
        date_label = QLabel("Date:")
        date_label.setStyleSheet(label_style)
        link_label = QLabel("Link:")
        link_label.setStyleSheet(label_style)
        
        # Add fields to form layout
        form_layout.addRow(container_label, self.container_input)
        form_layout.addRow(item_label, self.item_input)
        form_layout.addRow(title_label, self.title_input)
        form_layout.addRow(date_label, self.date_input)
        form_layout.addRow(link_label, self.link_input)
        
        # Add form to selector section
        selector_layout.addLayout(form_layout)
        
        # Add re-extract button with improved styling
        reextract_btn = QPushButton("Re-extract with these selectors")
        reextract_btn.setCursor(Qt.PointingHandCursor)
        reextract_btn.setStyleSheet("background-color: #4a86e8; color: white; border-radius: 4px; padding: 8px 15px; font-weight: bold; font-size: 16px;")
        reextract_btn.clicked.connect(self.reextract_with_selectors)
        selector_layout.addWidget(reextract_btn)
        
        # Add selector section to results layout
        self.results_layout.addWidget(selector_section)
        
        # 创建一个边框容器包裹滚动区域
        self.border_container = QWidget()
        self.border_container.setObjectName("results_border_container")
        self.border_container.setStyleSheet("""
            #results_border_container {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 0px;
            }
        """)
        border_layout = QVBoxLayout(self.border_container)
        border_layout.setContentsMargins(5, 5, 5, 5)  # 添加内边距，使边框有一定间隔
        
        # Create scroll area for results with improved style
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #ffffff;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #cdcdcd;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #808080;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Create content widget for results
        self.results_content = QWidget()
        self.results_content.setStyleSheet("""
            background-color: white;
        """)
        self.results_content_layout = QVBoxLayout(self.results_content)
        self.results_content_layout.setSpacing(10)  # 调整间距
        self.results_content_layout.setContentsMargins(4, 8, 8, 8)  # 减小左侧内边距
        
        # Set scroll content
        self.results_scroll.setWidget(self.results_content)
        border_layout.addWidget(self.results_scroll)
        
        # 将边框容器添加到结果布局
        self.results_layout.addWidget(self.border_container, 1)  # 1表示可拉伸
        
        # Buttons for the results panel
        buttons_layout = QHBoxLayout()
        
        # Save button
        self.save_results_btn = QPushButton("Save Results & Selectors")
        self.save_results_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
        """)
        self.save_results_btn.clicked.connect(self.save_results)
        buttons_layout.addWidget(self.save_results_btn)
        
        # Hide button
        self.hide_results_btn = QPushButton("Hide")
        self.hide_results_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.hide_results_btn.clicked.connect(lambda: self.toggle_results_panel(False))
        buttons_layout.addWidget(self.hide_results_btn)
        
        self.results_layout.addLayout(buttons_layout)
        
        # Add webview and results panel to horizontal layout
        h_layout.addWidget(webview_container, 7)  # 70% of width
        h_layout.addWidget(self.results_panel, 3)  # 30% of width
        
        # 创建一个主背景窗口
        self.main_window = QWidget()
        self.main_window.setObjectName("main_window")
        self.main_window.setStyleSheet("""
            #main_window {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
        """)
        
        # 创建主窗口的布局
        main_window_layout = QVBoxLayout(self.main_window)
        main_window_layout.setContentsMargins(0, 0, 0, 0)
        main_window_layout.setSpacing(0)
        
        # 添加标题栏和内容窗口
        main_window_layout.addWidget(self.title_bar)
        main_window_layout.addWidget(main_content)
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.main_window)

        self.results_panel.setObjectName("results_panel")
    
    def toggle_results_panel(self, show=True):
        """Show or hide the results panel"""
        self.results_panel.setVisible(show)
        
        # Get the main content through the main window
        main_content = self.main_window.layout().itemAt(1).widget()
        h_layout = main_content.layout()
        
        if show:
            h_layout.setStretch(0, 6)  # webview gets 60%
            h_layout.setStretch(1, 4)  # results panel gets 40%
        else:
            h_layout.setStretch(0, 1)  # webview gets 100%
            h_layout.setStretch(1, 0)  # results panel gets 0%
    
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
                        border: 3px solid rgba(255,0,0,0.8) !important;
                        background-color: rgba(255,235,235,0.1) !important;
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
                        border: 1px solid #27ae60;
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
            self.status_message.setText("Error: Received empty HTML content")
            self.status_message.setStyleSheet("color: #e74c3c; font-weight: bold;")
            return

        self.selected_container = html
        self.status_message.setText("Container selected! Analyzing content...")
        self.status_message.setStyleSheet("color: #2980b9; font-weight: bold;")
        
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
        """, self.set_selectors)
    
    def set_selectors(self, selectors):
        """Set the selectors in the form and extract data"""
        if not selectors:
            QMessageBox.critical(self, "Error", "Could not find valid list container")
            self.status_message.setText("Error: Could not find valid list container")
            self.status_message.setStyleSheet("color: #e74c3c; font-weight: bold; background-color: transparent;")
            return
        
        # Store the current selectors
        self.current_selectors = selectors
        
        # Update selector form fields
        self.container_input.setText(selectors["container"])
        self.item_input.setText(selectors["item"])
        self.title_input.setText(selectors["title"]) 
        self.date_input.setText(selectors["date"])
        self.link_input.setText(selectors["link"])
        
        # Continue with data extraction
        self.extract_data(selectors)
    
    def reextract_with_selectors(self):
        """Re-extract data using the edited selectors"""
        # Get the selectors from the form
        new_selectors = {
            "container": self.container_input.text(),
            "item": self.item_input.text(),
            "title": self.title_input.text(),
            "date": self.date_input.text(),
            "link": self.link_input.text()
        }
        
        # Make sure we have valid selectors
        if not new_selectors["container"] or not new_selectors["item"]:
            QMessageBox.critical(self, "Error", "Container or item selector cannot be empty")
            return
        
        # Update current selectors
        self.current_selectors = new_selectors
        
        # Extract data with new selectors
        self.extract_data(new_selectors)

    def extract_data(self, selectors):
        if not selectors:
            QMessageBox.critical(self, "Error", "Could not find valid list container")
            self.status_message.setText("Error: Could not find valid list container")
            self.status_message.setStyleSheet("color: #e74c3c; font-weight: bold; background-color: transparent;")
            return

        print(f"使用选择器: {selectors}")
        self.status_message.setText("Extracting data from selected container...")
        self.status_message.setStyleSheet("color: #2980b9; font-weight: bold; background-color: transparent;")
        
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
        """显示提取结果到右侧面板"""
        if not results or len(results) == 0:
            QMessageBox.information(self, "Information", "No results found")
            self.status_message.setText("No results found. Try selecting a different container.")
            self.status_message.setStyleSheet("color: #e74c3c; font-weight: bold; background-color: transparent;")
            
            # Show empty state in results panel
            self.clear_results()
            return
        
        self.status_message.setText(f"Successfully extracted {len(results)} items!")
        self.status_message.setStyleSheet("color: #27ae60; font-weight: bold; background-color: transparent;")
        self.results = results
        
        # Clear previous results
        while self.results_content_layout.count():
            item = self.results_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Update count label with animation hint
        self.count_label.setText(f"{len(results)} results found")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 20px; color: white; background-color: transparent; border: none; padding: 0px;")
        
        # 设置平滑滚动属性 - 修复方法
        self.results_scroll.verticalScrollBar().setSingleStep(10)
        self.results_scroll.horizontalScrollBar().setSingleStep(10)
        
        # Add new results
        for item in results:
            title = item.get('title', '')
            link = item.get('link', '')
            date = item.get('date', '')
            
            # Create a card-style frame for each result with simple styling
            result_frame = QWidget()
            result_frame.setObjectName("result_card")
            result_frame.setStyleSheet("""
                background-color: white; 
                border-radius: 6px; 
                border: 1px solid #e0e0e0; 
                margin-bottom: 12px;
                margin-left: 2px;
            """)
            result_frame.setMaximumWidth(450)  # 限制卡片最大宽度
            
            result_layout = QVBoxLayout(result_frame)
            result_layout.setSpacing(4)  # 减小元素间距
            result_layout.setContentsMargins(12, 12, 12, 12)
            
            # 创建标题标签 - 始终显示完整标题
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 16px; background-color: transparent; border: none; padding: 0px;")
            title_label.setWordWrap(True)  # 启用自动换行
            title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            title_label.setCursor(Qt.IBeamCursor)  # 设置文本选择光标
            title_label.setToolTip(title)  # 添加工具提示，鼠标悬停时显示完整标题
            title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            result_layout.addWidget(title_label)
            
            # 简化日期显示：直接放在标题下方
            if date:
                date_text = QLabel(f"📅 {date}")
                date_text.setStyleSheet("color: #7f8c8d; font-size: 14px; background-color: transparent; border: none; padding: 0px; margin-top: 0px;")
                result_layout.addWidget(date_text)
            
            # Separator line
            separator = QWidget()
            separator.setFixedHeight(1)
            separator.setStyleSheet("background-color: #f0f0f0; border: none;")
            result_layout.addWidget(separator)
            
            # 简化链接显示：直接放在分隔线下方
            if link:
                # 截断长链接
                link_display = link
                max_display_len = min(45, max(20, len(link)))
                if len(link) > max_display_len:
                    link_display = link[:max_display_len-3] + "..."
                
                # 创建水平布局
                link_container = QWidget()
                link_container.setStyleSheet("background-color: white; border: none;")
                link_layout = QHBoxLayout(link_container)
                link_layout.setContentsMargins(0, 2, 0, 0)  # 减少上边距
                link_layout.setSpacing(4)
                
                # 链接文本
                link_text = QLabel(f"🔗 <a href='{link}' style='color:#3498db; text-decoration:none;'>{link_display}</a>")
                link_text.setOpenExternalLinks(True)
                link_text.setTextInteractionFlags(Qt.TextBrowserInteraction)
                link_text.setStyleSheet("font-size: 14px; background-color: transparent; border: none; padding: 0px;")
                link_text.setToolTip(link)  # 添加工具提示，鼠标悬停时显示完整链接
                link_layout.addWidget(link_text, 1)
                
                # 复制按钮
                copy_btn = QToolButton()
                copy_btn.setToolTip("Copy link to clipboard")
                copy_btn.setText("📋")
                copy_btn.setCursor(Qt.PointingHandCursor)
                copy_btn.setStyleSheet("border: none; background: transparent; font-size: 15px; color: #7f8c8d;")
                copy_btn.setProperty("url", link)
                copy_btn.clicked.connect(self.copy_to_clipboard)
                link_layout.addWidget(copy_btn)
                
                result_layout.addWidget(link_container)
            
            # Add result to layout
            self.results_content_layout.addWidget(result_frame)
        
        # Add bottom padding
        self.results_content_layout.addStretch()
        
        # Ensure all QLabel widgets have no border
        for widget in self.results_panel.findChildren(QLabel):
            current_style = widget.styleSheet()
            if "border: none" not in current_style:
                widget.setStyleSheet(current_style + "; border: none; padding: 0px; margin: 0px;")
        
        # Show the results panel
        self.toggle_results_panel(True)

    def copy_to_clipboard(self):
        """Copy the URL to clipboard when copy button is clicked"""
        # Get the URL from the sender's custom property
        sender = self.sender()
        if sender and sender.property("url"):
            url = sender.property("url")
            
            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
            
            # Brief visual feedback
            sender.setText("✓")
            QTimer.singleShot(1000, lambda: sender.setText("📋"))

    def mousePressEvent(self, event):
        # Check if the click is on the title bar
        if self.title_bar.geometry().contains(event.pos()):
            self.drag_pos = event.globalPos()
        
    def mouseMoveEvent(self, event):
        if self.drag_pos:
            delta = event.globalPos() - self.drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def save_results(self):
        """Save the extracted results to a file"""
        if not self.results or len(self.results) == 0:
            QMessageBox.information(self, "提示", "没有结果可以保存")
            return
        
        from PyQt5.QtWidgets import QFileDialog
        import csv
        import os
        import re
        
        # First, save the selectors to config.yaml
        try:
            # Check if yaml module is available
            if yaml is None:
                raise ImportError("PyYAML package is not installed. Please install it with 'pip install pyyaml'")
                
            # Get current URL
            current_url = self.webview.url().toString()
            
            # Extract domain from URL for identification
            domain_match = re.search(r'https?://([^/]+)', current_url)
            if domain_match:
                domain = domain_match.group(1)
            else:
                domain = current_url
                
            # Prepare selectors data
            selector_data = {
                "container": self.container_input.text(),
                "link": self.link_input.text(),
                "title": self.title_input.text(),
                "date": self.date_input.text()
            }
            
            site_data = {
                "url": current_url,
                "output_file": f"{domain.replace('.', '_')}.xml",
                "selector": selector_data
            }
            
            # Check if config file exists
            config_path = "config.yaml"
            config_data = {"sites": []}
            
            if os.path.exists(config_path):
                # Read existing config
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {"sites": []}
                
                # Ensure 'sites' key exists
                if "sites" not in config_data:
                    config_data["sites"] = []
                
                # Check if site already exists
                site_updated = False
                for i, site in enumerate(config_data["sites"]):
                    if re.search(domain, site.get("url", "")):
                        # Update existing site
                        config_data["sites"][i]["selector"] = selector_data
                        site_updated = True
                        break
                
                # Add new site if not found
                if not site_updated:
                    config_data["sites"].append(site_data)
            else:
                # Create new config with this site
                config_data["sites"].append(site_data)
            
            # Write config
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            QMessageBox.information(self, "Success", f"Selectors saved to {config_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save selectors: {str(e)}")
            return
            
        # Ask for file location for results
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", "CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Get file extension
            _, ext = os.path.splitext(file_path)
            
            # Save as CSV
            if ext.lower() == '.csv':
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Write header
                    writer.writerow(['Title', 'Link', 'Date'])
                    # Write data
                    for item in self.results:
                        writer.writerow([
                            item.get('title', ''),
                            item.get('link', ''),
                            item.get('date', '')
                        ])
            # Save as TXT
            elif ext.lower() == '.txt':
                with open(file_path, 'w', encoding='utf-8') as f:
                    for item in self.results:
                        f.write(f"Title: {item.get('title', '')}\n")
                        f.write(f"Link: {item.get('link', '')}\n")
                        f.write(f"Date: {item.get('date', '')}\n")
                        f.write('-' * 50 + '\n')
            else:
                # Default to CSV if no extension or unknown
                with open(file_path + '.csv', 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Title', 'Link', 'Date'])
                    for item in self.results:
                        writer.writerow([
                            item.get('title', ''),
                            item.get('link', ''),
                            item.get('date', '')
                        ])
            
            QMessageBox.information(self, "Success", f"Results saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save results: {str(e)}")

    def clear_results(self):
        """Clear the current results"""
        self.results = []
        
        # Clear the results panel
        while self.results_content_layout.count():
            item = self.results_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Update the count label
        self.count_label.setText("Results cleared")
        
        # Add a placeholder message with better styling
        placeholder_widget = QWidget()
        placeholder_widget.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #e0e0e0; margin: 10px;")
        placeholder_layout = QVBoxLayout(placeholder_widget)
        placeholder_layout.setContentsMargins(15, 25, 15, 25)
        
        empty_icon = QLabel("🔍")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet("font-size: 60px; color: #bdc3c7; background-color: transparent;")
        
        placeholder_text = QLabel("No results to display")
        placeholder_text.setAlignment(Qt.AlignCenter)
        placeholder_text.setStyleSheet("color: #7f8c8d; font-size: 16px; font-weight: bold; background-color: transparent;")
        
        placeholder_subtext = QLabel("Hover over a list container and press Enter to extract data")
        placeholder_subtext.setAlignment(Qt.AlignCenter)
        placeholder_subtext.setStyleSheet("color: #95a5a6; font-size: 14px; background-color: transparent;")
        placeholder_subtext.setWordWrap(True)
        
        placeholder_layout.addStretch()
        placeholder_layout.addWidget(empty_icon)
        placeholder_layout.addWidget(placeholder_text)
        placeholder_layout.addWidget(placeholder_subtext)
        placeholder_layout.addStretch()
        
        self.results_content_layout.addWidget(placeholder_widget)

class TabStyleTitleBar(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setFixedHeight(35)
        self.setStyleSheet("background-color: transparent;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        
        # Title label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            color: #333333;
            font-size: 14px;
            font-weight: bold;
            background-color: transparent;
            padding-left: 5px;
        """)
        
        # Close button
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #555555;
                border: none;
                border-radius: 10px;
                margin-right: 2px;
            }
            QPushButton:hover {
                background-color: #ff4444;
                color: white;
            }
        """)
        
        # Add icon and title to layout
        icon_label = QLabel()
        icon_label.setFixedSize(16, 16)
        icon_label.setStyleSheet("background-color: transparent; padding: 0px; margin: 0px;")
        icon_label.setText("⚙")
        
        layout.addWidget(icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.close_btn)
        
        # Setup cursor for draggable area
        self.setCursor(Qt.ArrowCursor)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Define the tab path
        path = QPainterPath()
        path.moveTo(0, self.height())
        path.lineTo(0, 6)
        path.quadTo(0, 0, 6, 0)
        path.lineTo(self.width() - 6, 0)
        path.quadTo(self.width(), 0, self.width(), 6)
        path.lineTo(self.width(), self.height())
        
        # Fill with gradient
        painter.fillPath(path, QColor(240, 240, 240))
        
        # Draw the border
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.drawPath(path)
        
        # Draw the bottom line for non-active tabs (here we assume this is the active tab)
        # If you want to add inactive tabs, you'd draw a line at the bottom of those

if __name__ == '__main__':
    app = QApplication(sys.argv)
    browser = CompactBrowser(url="https://kjj.gz.gov.cn/xxgk/zcfg/index.html")
    browser.show()
    sys.exit(app.exec_())

    # https://kjj.gz.gov.cn/xxgk/zcfg/
    # https://gdstc.gd.gov.cn/zwgk_n/tzgg/
    # https://www.hp.gov.cn/gzhpkj/gkmlpt/index