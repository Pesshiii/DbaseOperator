from PyQt5 import QtCore, QtGui, QtWidgets
import sqlite3
import os
from typing import Dict, List, Union, Optional, Tuple
import pandas as pd



#################################################################
#################################################################
################################################################# USEFULL FUNNCTIONS
#################################################################
#################################################################


def throw_exeption(parent, exeption:str):
    QtWidgets.QMessageBox.warning(parent, "Внимание", exeption)

################################################################
################################################################
################################################################    WORK WITH SQLITE
################################################################
################################################################

def get_table_data(
    parent,
    db_path: str,
    table_name: str,
    columns: Optional[List[str]] = None,
    where_clause: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    return_type: str = "list"  # "list", "dict", or "dataframe"
) -> Union[List[Tuple], List[Dict], pd.DataFrame]:
    """
    Retrieves data from a SQLite database table with flexible options.
    
    Args:
        parent: Parent widget for exception handling
        db_path: Path to SQLite database file
        table_name: Name of table to query
        columns: List of columns to select (None for all columns)
        where_clause: WHERE conditions (without 'WHERE' keyword)
        order_by: ORDER BY clause (without 'ORDER BY' keyword)
        limit: Maximum number of rows to return
        return_type: Format of returned data - "list", "dict", or "dataframe"
    
    Returns:
        Data in specified format (list of tuples, list of dicts, or DataFrame)
    
    Raises:
        ValueError: For invalid return_type or other input errors
        sqlite3.Error: For database errors
    """
    # Validate return type
    if return_type not in ["list", "dict", "dataframe"]:
        raise throw_exeption(parent, "return_type must be 'list', 'dict', or 'dataframe'")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # For dict output
        cursor = conn.cursor()
        
        # Build SELECT clause
        select_clause = "*" if columns is None else ", ".join(columns)
        
        # Build base query
        query = f"SELECT {select_clause} FROM {table_name}"
        
        # Add WHERE clause if provided
        if where_clause:
            query += f" WHERE {where_clause}"
            
        # Add ORDER BY if provided
        if order_by:
            query += f" ORDER BY {order_by}"
            
        # Add LIMIT if provided
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        cursor.execute(query)
        
        # Fetch results based on return type
        if return_type == "list":
            results = cursor.fetchall()
        elif return_type == "dict":
            results = [dict(row) for row in cursor.fetchall()]
        else:  # dataframe
            results = pd.read_sql_query(query, conn)
            
        return results
        
    except sqlite3.Error as e:
        throw_exeption(parent, f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def insert_into_table(
    parent,
    db_path: str,
    table_name: str,
    columns: List[str],
    values: List[List[Union[str, int, float, bool, None]]],
    batch_size: int = 100
) -> int:
    """
    Inserts multiple rows into a SQLite table efficiently.
    
    Args:
        db_path: Path to SQLite database file
        table_name: Name of table to insert into
        columns: List of column names (e.g., ['name', 'age', 'email'])
        values: 2D list of values to insert (each inner list is a row)
        batch_size: Number of rows to insert in each transaction
    
    Returns:
        Number of rows successfully inserted
    """
    if not values:
        throw_exeption(parent, "Warning: No values provided to insert")
        return 0

    if len(columns) != len(values[0]):
        throw_exeption(parent, "Number of columns doesn't match values structure")
        return 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create parameter placeholders (?, ?, ?) based on column count
        placeholders = ', '.join(['?'] * len(columns))
        columns_str = ', '.join(columns)
        sql = f"""INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})"""
        
        total_inserted = 0
        
        # Insert in batches for better performance with large datasets
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            cursor.executemany(sql, batch)
            total_inserted += len(batch)
            conn.commit()
            
        return total_inserted

    except sqlite3.Error as e:
        throw_exeption(parent, f"Database error: {e}")
        conn.rollback()
        return 0
        
    finally:
        if conn:
            conn.close()

def getOpenFilesAndDirs(parent=None, caption='', directory='', 
                        filter='', initialFilter='', options=None):
    """
        Solution from:
            stackoverflow.com/questions/64336575/select-a-file-or-a-folder-in-qfiledialog-pyqt5
    """
    def updateText():
        # update the contents of the line edit widget with the selected files
        selected = []
        for index in view.selectionModel().selectedRows():
            selected.append('"{}"'.format(index.data()))
        lineEdit.setText(' '.join(selected))

    dialog = QtWidgets.QFileDialog(parent, windowTitle=caption)
    dialog.setFileMode(dialog.ExistingFiles)
    if options:
        dialog.setOptions(options)
    dialog.setOption(dialog.DontUseNativeDialog, True)
    if directory:
        dialog.setDirectory(directory)
    if filter:
        dialog.setNameFilter(filter)
        if initialFilter:
            dialog.selectNameFilter(initialFilter)

    # by default, if a directory is opened in file listing mode, 
    # QFileDialog.accept() shows the contents of that directory, but we 
    # need to be able to "open" directories as we can do with files, so we 
    # just override accept() with the default QDialog implementation which 
    # will just return exec_()
    dialog.accept = lambda: QtWidgets.QDialog.accept(dialog)

    # there are many item views in a non-native dialog, but the ones displaying 
    # the actual contents are created inside a QStackedWidget; they are a 
    # QTreeView and a QListView, and the tree is only used when the 
    # viewMode is set to QFileDialog.Details, which is not this case
    stackedWidget = dialog.findChild(QtWidgets.QStackedWidget)
    view = stackedWidget.findChild(QtWidgets.QListView)
    view.selectionModel().selectionChanged.connect(updateText)

    lineEdit = dialog.findChild(QtWidgets.QLineEdit)
    # clear the line edit contents whenever the current directory changes
    dialog.directoryEntered.connect(lambda: lineEdit.setText(''))

    dialog.exec_()
    return dialog.selectedFiles()

def setupDB(db_name, file_path, mainwidget: QtWidgets.QMainWindow):
    """
    Creates a SQLite database with the given name at the specified path.
    
    Args:
        db_name (str): Name of the database (without .db extension)
        file_path (str, optional): Directory path where the database should be created.
                                  If None, creates in current working directory.
    
    Returns:
        str: Full path to the created database file
        None: If creation failed
    """

    if db_name == '':
        QtWidgets.QMessageBox.warning(mainwidget, "Внимание", "Укажите корректное название")
        return None
    if file_path == '':
        QtWidgets.QMessageBox.warning(mainwidget, "Внимание", "Путь к файлу не может быть пустым")
        return None
        
    try:
        # Create directory if it doesn't exist
        os.makedirs(file_path, exist_ok=True)
        
        # Construct full database path
        db_path = os.path.join(file_path, f"{db_name}.db")
        
        # Connect to database (creates it if doesn't exist)
        conn = sqlite3.connect(db_path)
        conn.close()
        
        return db_path
    
    except Exception as e:
        QtWidgets.QMessageBox.warning(mainwidget, "Внимание", f"Ошибка при создании базы данных: {e}")
        return None

def createTable(parent, db_path, table_name, columns: Dict[str, str], primary_key = None):
    """
    Creates a table in an SQLite database with specified columns and data types.
    
    Args:
        db_path (str): Path to the SQLite database file
        table_name (str): Name of the table to create
        columns (Dict[str, str]): Dictionary where keys are column names and values are SQLite data types
                                 (e.g., {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT', 'age': 'INTEGER'})
    
    Returns:
        bool: True if table was created successfully, False otherwise
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        
        # Create the column definitions string
        column_defs = ', '.join([f'"{col_name}" {data_type}' for col_name, data_type in columns.items()])
        
        # Execute the CREATE TABLE statement
        create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({column_defs}'
        if not primary_key == None:
            create_table_sql += f", PRIMARY KEY {primary_key}"
        create_table_sql += ")"
        cursor.execute(create_table_sql)
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print(parent, f"Table '{table_name}' created successfully with columns: {list(columns.keys())}")
        return True
    
    except sqlite3.Error as e:
        throw_exeption(parent, f"Error creating table: {e}")
        return False



################################################################
################################################################ 
################################################################    WORK WITH PYQT FOR GUI
################################################################ 
################################################################




def to_opener():
    """
        Return mainwidget to the first state.
        Can be accessed through Create_db on rejected clicked
    """
    pass

class Ui_Create_db(object):
    def setupUi(self, Create_db: QtWidgets.QDialog, parent):
        """
            Create dialog window for constructing your own database
        """
        Create_db.resize(900, 500)
        self.parent = parent
        self.dialog_window = Create_db
        self.verticalLayout = QtWidgets.QVBoxLayout(Create_db)
        self.verticalLayout.setObjectName("verticalLayout")
        self.db_name = QtWidgets.QHBoxLayout()
        self.db_name.setObjectName("db_name")
        self.db_name_lable = QtWidgets.QLabel(Create_db)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.db_name_lable.sizePolicy().hasHeightForWidth())
        self.db_name_lable.setSizePolicy(sizePolicy)
        self.db_name_lable.setMaximumSize(QtCore.QSize(180, 100))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.db_name_lable.setFont(font)
        self.db_name_lable.setObjectName("db_name_lable")
        self.db_name.addWidget(self.db_name_lable)
        self.db_name_line = QtWidgets.QLineEdit(Create_db)
        self.db_name_line.setObjectName("db_name_line")
        self.db_name.addWidget(self.db_name_line)
        self.verticalLayout.addLayout(self.db_name)
        self.file_input = QtWidgets.QHBoxLayout()
        self.file_input.setObjectName("file_input")
        self.file_input_lable = QtWidgets.QLabel(Create_db)
        self.file_input_lable.setMaximumSize(QtCore.QSize(180, 16777215))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.file_input_lable.setFont(font)
        self.file_input_lable.setObjectName("file_input_lable")
        self.file_input.addWidget(self.file_input_lable)
        self.file_input_line = QtWidgets.QLineEdit(Create_db)
        self.file_input_line.setEnabled(False)
        self.file_input_line.setObjectName("file_input_line")
        self.file_input.addWidget(self.file_input_line)
        self.file_input_button = QtWidgets.QPushButton(Create_db)
        self.file_input_button.setMaximumSize(QtCore.QSize(50, 16777215))
        self.file_input_button.setObjectName("file_input_button")
        self.file_input_button.clicked.connect(self.on_file_input)
        self.file_input.addWidget(self.file_input_button)
        self.verticalLayout.addLayout(self.file_input)
        self.add_column = QtWidgets.QHBoxLayout()
        self.add_column.setObjectName("add_column")
        self.label = QtWidgets.QLabel(Create_db)
        self.label.setObjectName("label")
        self.label.setFont(font)
        self.add_column.addWidget(self.label)
        self.add_column_button = QtWidgets.QPushButton(Create_db)
        self.add_column_button.setMaximumSize(QtCore.QSize(80, 16777215))
        self.add_column_button.setObjectName("add_column_button")
        def on_add_column():
            # SQLite data type options
            type_options = ["TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "BOOLEAN", "DATE"]
            
            cur_row = self.table.rowCount()
            self.table.setRowCount(cur_row+1)
            # SQL column name (editable, defaults to Excel name)
            sql_item = QtWidgets.QTableWidgetItem("Имя столбца")
            self.table.setItem(cur_row, 0, sql_item)

            
            checkbox = QtWidgets.QCheckBox()
            self.table.setCellWidget(cur_row, 2, checkbox)
            
            desc_item = QtWidgets.QTableWidgetItem("Описание")
            self.table.setItem(cur_row, 3, desc_item)
            
            # Data type combo box
            type_combo = QtWidgets.QComboBox()
            type_combo.addItems(type_options)
            
            self.table.setCellWidget(cur_row, 1, type_combo)
        self.add_column_button.clicked.connect(on_add_column)
        self.add_column.addWidget(self.add_column_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.add_column.addItem(spacerItem)
        self.verticalLayout.addLayout(self.add_column)
        self.table = QtWidgets.QTableWidget(Create_db)
        self.table.setObjectName("table")
        self.table.setColumnCount(4)
        self.table.setRowCount(2)
        self.table.setHorizontalHeaderLabels(["Название", "Тип данных", "Обязательное\nполе", "Описание"])
        self.table.horizontalHeader().setStretchLastSection(True)
        item1=QtWidgets.QTableWidgetItem("Поставщик")
        item1.setFlags(item1.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(0,0,item1)
        item3=QtWidgets.QTableWidgetItem("Номер поставщика (обязательно, присваевается автоматически)")
        item3.setFlags(item3.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(0,3,item3)
        type_options = ["TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC", "BOOLEAN", "DATE"]
        type_combo1 = QtWidgets.QComboBox()
        type_combo1.addItems(["INTEGER"])
        type_combo1.setEnabled(False)
        self.table.setCellWidget(0, 1, type_combo1)
        radio1 = QtWidgets.QCheckBox()
        radio1.setEnabled(False)
        radio1.setChecked(True)
        self.table.setCellWidget(0 , 2, radio1)
        item2=QtWidgets.QTableWidgetItem("Артикул")
        item2.setFlags(item2.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(1,0,item2)
        item4=QtWidgets.QTableWidgetItem("Артикул у поставщика (обязательно, без повторений)")
        item4.setFlags(item4.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(1,3,item4)
        type_combo2 = QtWidgets.QComboBox()
        type_combo2.addItems(type_options[:2])
        self.table.setCellWidget(1, 1, type_combo2)
        radio2 = QtWidgets.QCheckBox()
        radio2.setEnabled(False)
        radio2.setChecked(True)
        self.table.setCellWidget(1, 2, radio2)
        self.verticalLayout.addWidget(self.table)
        self.dialog_button = QtWidgets.QDialogButtonBox(Create_db)
        self.dialog_button.setOrientation(QtCore.Qt.Horizontal)
        self.dialog_button.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.dialog_button.setObjectName("dialog_button")
        self.verticalLayout.addWidget(self.dialog_button)
        self.dialog_button.accepted.connect(self.create_db)
        self.dialog_button.rejected.connect(Create_db.close)
        self.retranslateUi(Create_db)
        QtCore.QMetaObject.connectSlotsByName(Create_db)

    def create_db(self):
        path = setupDB(self.db_name_line.text(), self.file_input_line.text(), SearchPrice)
        if path is None:
            return
        self.createPrice(path)
        self.parent.path = path
        self.parent.on_open_db()
        self.dialog_window.close()
    
    def on_file_input(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog_window,
            "Файл для базы данных",
            "C:\\",
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            self.file_input_line.setText(folder_path)
    
    def createPrice(self, path: str):
        """
            Accessed only through self.create_db
        """
        columns = {'Название' : "TEXT PRIMARY KEY",
                    'Тип данных': "TEXT NOT NULL",
                    'Обязательное\nполе': "INTEGER",
                    'Описание':"TEXT"
                    }
        if not createTable(self.dialog_window, path, "ОПИСАНИЕ ПРАЙСА", columns):
            return
        insert = []
        for row in range(self.table.rowCount()):
            insert.append([self.table.item(row, 0).text(), self.table.cellWidget(row, 1).currentText(), int(self.table.cellWidget(row, 2).isChecked()), self.table.item(row, 3).text()])
        insert_into_table(self.dialog_window, path, "ОПИСАНИЕ ПРАЙСА", ['"Название"', '"Тип данных"', '"Обязательное\nполе"', '"Описание"'], insert, 10)
        newtable = {}
        for column in insert:
            buf =  column[1]
            if column[2] == 1: buf+=" NOT NULL"
            newtable.update({column[0]:buf})
        createTable(self.dialog_window, path, "ПРАЙС", newtable, (insert[0][0], insert[1][0]))
            
            


    def retranslateUi(self, Create_db):
        _translate = QtCore.QCoreApplication.translate
        Create_db.setWindowTitle(_translate("Create_db", "Dialog"))
        self.db_name_lable.setText(_translate("Create_db", "Название базы даных:"))
        self.file_input_lable.setText(_translate("Create_db", "Расположение файла:"))
        self.file_input_button.setText(_translate("Create_db", "..."))
        self.label.setText(_translate("Create_db", "Добавить столбцы: "))
        self.add_column_button.setToolTip(_translate("Create_db", "Добавить столбец"))
        self.add_column_button.setText(_translate("Create_db", "Добавить"))


class Ui_OpenerSearchPrice(object):
    def on_create_db(self):
        create_db_window = QtWidgets.QDialog(self.MainWindow)
        create_db = Ui_Create_db()
        create_db.setupUi(create_db_window, self)
        create_db_window.show()

    def on_open_db(self):
        print(self.path)
        if self.path == None or not self.path[-3:] == ".db":
            file, check = QtWidgets.QFileDialog.getOpenFileName(
            self.MainWindow,
            "QFileDialog.getOpenFileName()",
            "C:\\",
            self.MainWindow.tr(
                'Файл базы данных (*.db);;'))
            if check:
                self.path = file
        print(get_table_data(self.MainWindow, self.path, "ПРАЙС", return_type="dataframe"))

    def setupUi(self, OpenerSearchPrice):
        OpenerSearchPrice.setObjectName("OpenerSearchPrice")
        OpenerSearchPrice.resize(2000, 1000)
        self.MainWindow = OpenerSearchPrice
        self.centralwidget = QtWidgets.QWidget(OpenerSearchPrice)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.label = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setFamily("Segoe UI Light")
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(True)
        self.path = None
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.verticalLayout.addLayout(self.horizontalLayout)
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem2)
        OpenerSearchPrice.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(OpenerSearchPrice)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 909, 26))
        self.menubar.setObjectName("menubar")
        self.database = QtWidgets.QMenu(self.menubar)
        self.database.setObjectName("database")
        self.price = QtWidgets.QMenu(self.menubar)
        self.price.setEnabled(False)
        self.price.setObjectName("price")
        self.table = QtWidgets.QMenu(self.menubar)
        self.table.setEnabled(False)
        self.table.setObjectName("table")
        OpenerSearchPrice.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(OpenerSearchPrice)
        self.statusbar.setObjectName("statusbar")
        OpenerSearchPrice.setStatusBar(self.statusbar)
        self.db_create = QtWidgets.QAction(OpenerSearchPrice)
        self.db_create.setObjectName("db_create")
        self.db_create.triggered.connect(self.on_create_db)
        self.db_open = QtWidgets.QAction(OpenerSearchPrice)
        self.db_open.setObjectName("db_open")
        self.db_open.triggered.connect(self.on_open_db)
        self.db_change = QtWidgets.QAction(OpenerSearchPrice)
        self.db_change.setEnabled(False)
        self.db_change.setObjectName("db_change")
        self.db_export = QtWidgets.QAction(OpenerSearchPrice)
        self.db_export.setEnabled(False)
        self.db_export.setObjectName("db_export")
        self.price_update = QtWidgets.QAction(OpenerSearchPrice)
        self.price_update.setEnabled(True)
        self.price_update.setObjectName("price_update")
        self.price_reconfigure = QtWidgets.QAction(OpenerSearchPrice)
        self.price_reconfigure.setObjectName("price_reconfigure")
        self.table_add = QtWidgets.QAction(OpenerSearchPrice)
        self.table_add.setEnabled(False)
        self.table_add.setObjectName("table_add")
        self.table_reconfigure = QtWidgets.QAction(OpenerSearchPrice)
        self.table_reconfigure.setObjectName("table_reconfigure")
        self.database.addAction(self.db_create)
        self.database.addAction(self.db_open)
        self.database.addAction(self.db_change)
        self.database.addSeparator()
        self.database.addAction(self.db_export)
        self.price.addAction(self.price_update)
        self.price.addAction(self.price_reconfigure)
        self.table.addAction(self.table_add)
        self.table.addAction(self.table_reconfigure)
        self.menubar.addAction(self.database.menuAction())
        self.menubar.addAction(self.price.menuAction())
        self.menubar.addAction(self.table.menuAction())

        self.retranslateUi(OpenerSearchPrice)
        QtCore.QMetaObject.connectSlotsByName(OpenerSearchPrice)

    def retranslateUi(self, OpenerSearchPrice):
        _translate = QtCore.QCoreApplication.translate
        OpenerSearchPrice.setWindowTitle(_translate("OpenerSearchPrice", "MainWindow"))
        self.label.setText(_translate("OpenerSearchPrice", "Откройте или создайте новую базу данных для начала работы"))
        self.database.setTitle(_translate("OpenerSearchPrice", "База данных"))
        self.price.setTitle(_translate("OpenerSearchPrice", "Прайс"))
        self.table.setTitle(_translate("OpenerSearchPrice", "Таблица"))
        self.db_create.setText(_translate("OpenerSearchPrice", "Создать"))
        self.db_create.setToolTip(_translate("OpenerSearchPrice", "Создать новую"))
        self.db_open.setText(_translate("OpenerSearchPrice", "Открыть"))
        self.db_open.setToolTip(_translate("OpenerSearchPrice", "Открыть существующую"))
        self.db_change.setText(_translate("OpenerSearchPrice", "Редактировать"))
        self.db_change.setToolTip(_translate("OpenerSearchPrice", "Редактировать датабазу"))
        self.db_export.setText(_translate("OpenerSearchPrice", "Экспорт"))
        self.db_export.setToolTip(_translate("OpenerSearchPrice", "Экспорт датабазы"))
        self.price_update.setText(_translate("OpenerSearchPrice", "Обновить"))
        self.price_reconfigure.setText(_translate("OpenerSearchPrice", "Редактировать"))
        self.table_add.setText(_translate("OpenerSearchPrice", "Добавить"))
        self.table_reconfigure.setText(_translate("OpenerSearchPrice", "Редактировать"))



class Ui_SearchPrice(object):
    def setupUi(self, SearchPrice):
        SearchPrice.setObjectName("SearchPrice")
        SearchPrice.resize(909, 509)
        self.centralwidget = QtWidgets.QWidget(SearchPrice)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.searchArea = QtWidgets.QScrollArea(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.searchArea.sizePolicy().hasHeightForWidth())
        self.searchArea.setSizePolicy(sizePolicy)
        self.searchArea.setMinimumSize(QtCore.QSize(0, 200))
        self.searchArea.setWidgetResizable(True)
        self.searchArea.setObjectName("searchArea")
        self.searchAreaContents = QtWidgets.QWidget()
        self.searchAreaContents.setGeometry(QtCore.QRect(0, 0, 885, 198))
        self.searchAreaContents.setObjectName("searchAreaContents")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.searchAreaContents)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.searchArea.setWidget(self.searchAreaContents)
        self.verticalLayout.addWidget(self.searchArea)
        self.tableWidget = QtWidgets.QTableWidget(self.centralwidget)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(0)
        self.tableWidget.setRowCount(0)
        self.verticalLayout.addWidget(self.tableWidget)
        SearchPrice.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(SearchPrice)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 909, 26))
        self.menubar.setObjectName("menubar")
        self.database = QtWidgets.QMenu(self.menubar)
        self.database.setObjectName("database")
        self.price = QtWidgets.QMenu(self.menubar)
        self.price.setEnabled(False)
        self.price.setObjectName("price")
        self.table = QtWidgets.QMenu(self.menubar)
        self.table.setEnabled(False)
        self.table.setObjectName("table")
        SearchPrice.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(SearchPrice)
        self.statusbar.setObjectName("statusbar")
        SearchPrice.setStatusBar(self.statusbar)
        self.db_create = QtWidgets.QAction(SearchPrice)
        self.db_create.setObjectName("db_create")
        self.db_open = QtWidgets.QAction(SearchPrice)
        self.db_open.setObjectName("db_open")
        self.db_change = QtWidgets.QAction(SearchPrice)
        self.db_change.setEnabled(False)
        self.db_change.setObjectName("db_change")
        self.db_export = QtWidgets.QAction(SearchPrice)
        self.db_export.setEnabled(False)
        self.db_export.setObjectName("db_export")
        self.price_update = QtWidgets.QAction(SearchPrice)
        self.price_update.setEnabled(True)
        self.price_update.setObjectName("price_update")
        self.price_reconfigure = QtWidgets.QAction(SearchPrice)
        self.price_reconfigure.setObjectName("price_reconfigure")
        self.table_add = QtWidgets.QAction(SearchPrice)
        self.table_add.setEnabled(False)
        self.table_add.setObjectName("table_add")
        self.table_reconfigure = QtWidgets.QAction(SearchPrice)
        self.table_reconfigure.setObjectName("table_reconfigure")
        self.database.addAction(self.db_create)
        self.database.addAction(self.db_open)
        self.database.addAction(self.db_change)
        self.database.addSeparator()
        self.database.addAction(self.db_export)
        self.price.addAction(self.price_update)
        self.price.addAction(self.price_reconfigure)
        self.table.addAction(self.table_add)
        self.table.addAction(self.table_reconfigure)
        self.menubar.addAction(self.database.menuAction())
        self.menubar.addAction(self.price.menuAction())
        self.menubar.addAction(self.table.menuAction())

        self.retranslateUi(SearchPrice)
        QtCore.QMetaObject.connectSlotsByName(SearchPrice)

    def retranslateUi(self, SearchPrice):
        _translate = QtCore.QCoreApplication.translate
        SearchPrice.setWindowTitle(_translate("SearchPrice", "MainWindow"))
        self.database.setTitle(_translate("SearchPrice", "База данных"))
        self.price.setTitle(_translate("SearchPrice", "Прайс"))
        self.table.setTitle(_translate("SearchPrice", "Таблица"))
        self.db_create.setText(_translate("SearchPrice", "Создать"))
        self.db_create.setToolTip(_translate("SearchPrice", "Создать новую"))
        self.db_open.setText(_translate("SearchPrice", "Открыть"))
        self.db_open.setToolTip(_translate("SearchPrice", "Открыть существующую"))
        self.db_change.setText(_translate("SearchPrice", "Редактировать"))
        self.db_change.setToolTip(_translate("SearchPrice", "Редактировать датабазу"))
        self.db_export.setText(_translate("SearchPrice", "Экспорт"))
        self.db_export.setToolTip(_translate("SearchPrice", "Экспорт датабазы"))
        self.price_update.setText(_translate("SearchPrice", "Обновить"))
        self.price_reconfigure.setText(_translate("SearchPrice", "Редактировать"))
        self.table_add.setText(_translate("SearchPrice", "Добавить"))
        self.table_reconfigure.setText(_translate("SearchPrice", "Редактировать"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    SearchPrice = QtWidgets.QMainWindow()
    ui = Ui_OpenerSearchPrice()
    ui.setupUi(SearchPrice)
    SearchPrice.show()
    sys.exit(app.exec_())
