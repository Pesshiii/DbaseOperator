from PyQt5 import QtCore, QtGui, QtWidgets
import sqlite3
import os
from typing import Dict, List, Union, Optional, Tuple
import pandas as pd
from re import findall



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


def drop_table(database_path: str, table_name: str) -> None:
    """
    Drops a table from an SQLite database.
    
    Args:
        database_path (str): Path to the SQLite database file
        table_name (str): Name of the table to drop
        
    Raises:
        sqlite3.Error: If there's an error executing the SQL command
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        # Execute the DROP TABLE command
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # Commit the changes
        conn.commit()
        print(f"Table '{table_name}' dropped successfully.")
        
    except sqlite3.Error as e:
        print(f"Error dropping table: {e}")
        # Rollback in case of error
        if conn:
            conn.rollback()
        raise
        
    finally:
        # Close the connection
        if conn:
            conn.close()

def get_table_columns(db_path: str, table_name: str) -> List[str]:
    """
    Retrieves the column names of a specified table in an SQLite database.
    
    Args:
        db_path: Path to the SQLite database file
        table_name: Name of the table to inspect
    
    Returns:
        List of column names in the table
    
    Raises:
        sqlite3.Error: If there's an error accessing the database or table
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query the table's schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        
        # Extract column names from the result
        column_names = [column[1] for column in columns_info]
        
        return column_names
    
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Error fetching column names: {e}")
    
    finally:
        # Ensure connection is closed even if an error occurs
        if 'conn' in locals():
            conn.close()

def sort_table_by_relevancy(
    db_path: str,
    table_name: str,
    column_request_pairs: List[Tuple[str, str]],
    score: float,
    output_column: str = '*',
    limit: int = None
) -> pd.DataFrame:
    """
    Sorts an SQLite table by relevancy of columns to search requests.
    
    Args:
        db_path: Path to the SQLite database file
        table_name: Name of the table to query
        column_request_pairs: List of (column_name, search_request) tuples
        output_column: Column(s) to return in results (default: all columns)
        limit: Maximum number of results to return (default: no limit)
    
    Returns:
        List of tuples containing the query results sorted by relevancy
    """
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Build the relevancy scoring SQL expression
    relevancy_expr_parts = []
    for column, request in column_request_pairs:
        if not request.strip():
            continue
            
        # Use SQLite's LIKE operator for simple pattern matching
        # For more advanced search, you could use FTS (Full Text Search)
        sanitized_request = request.replace('%', '\\%').replace('_', '\\_')
        relevancy_part = f"""
            CASE WHEN {column} LIKE '%' || ? || '%' ESCAPE '\\' THEN 1 ELSE 0 END
        """
        relevancy_expr_parts.append(relevancy_part)
    
    if not relevancy_expr_parts:
        # No valid search requests, just return all rows unordered
        query = f"SELECT {output_column} FROM {table_name}"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return cursor.fetchall()
    
    relevancy_expr = " + ".join(relevancy_expr_parts)
    
    # Prepare the query parameters
    request_values = [request for _, request in column_request_pairs if request.strip()]
    
    # Build and execute the query
    query = f"""
        SELECT {output_column}, ({relevancy_expr}) AS relevancy_score
        FROM {table_name}
        WHERE relevancy_score > {score}
        ORDER BY relevancy_score DESC
    """

    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, request_values)
    results = cursor.fetchall()
    
    # Close the connection
    conn.close()
    
    # Return results without the relevancy score if output_column was specified
    return pd.DataFrame([result[:-1] for result in results], columns=get_table_columns(db_path, table_name))

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
        query = f"SELECT {select_clause} FROM \"{table_name}\""
        
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

        columns = [f'"{i}"' for i in columns]
        
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
        QtWidgets.QMessageBox.warning(mainwidget, "Внимание", "Имя базы данных не подходит")
        return None
    if file_path == '':
        QtWidgets.QMessageBox.warning(mainwidget, "Внимание", "Путь к файлу не может быть пустым")
        return None
        
    try:
        # Create directory if it doesn't exist
        os.makedirs(file_path,exist_ok=True)
        
        # Construct full database path
        if os.path.exists(f"{file_path}\\{db_name}.db"): raise Exception(f"База данных с таким именем уже существует")

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
        
        create_table_sql = f'CREATE TABLE "{table_name}" ({column_defs}'
        if not primary_key == None:
            primary_key = ", ".join([f'"{i}"' for i in primary_key])
            create_table_sql += f""", PRIMARY KEY ({primary_key})"""
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
################################################################    WORK WITH QT
################################################################ 
################################################################

def dataframe_to_qtablewidget(
    df: pd.DataFrame,
    table_widget: QtWidgets.QTableWidget,
    display_index: bool = False,
    stretch_columns: bool = True,
    alternate_row_colors: bool = True,
    header_alignment: QtCore.Qt.Alignment = QtCore.Qt.AlignLeft,
    data_alignment: QtCore.Qt.Alignment = QtCore.Qt.AlignLeft
) -> None:
    """
    Displays a pandas DataFrame in a QTableWidget.
    
    Args:
        df: Pandas DataFrame to display
        table_widget: QTableWidget instance to populate
        display_index: Whether to show the DataFrame index as first column
        stretch_columns: Whether to stretch columns to fill available space
        alternate_row_colors: Whether to use alternating row colors
        header_alignment: Alignment for header cells (Qt.AlignLeft/Center/Right)
        data_alignment: Alignment for data cells (Qt.AlignLeft/Center/Right)
    """
    # Clear existing content
    table_widget.clear()
    
    # Determine rows and columns
    n_rows, n_cols = df.shape
    if display_index:
        n_cols += 1  # Add extra column for index
    
    # Set table dimensions
    table_widget.setRowCount(n_rows)
    table_widget.setColumnCount(n_cols)
    
    # Set headers
    headers = []
    if display_index:
        headers.append("Index")  # Index column header
    
    headers.extend([f'{i}' for i in df.columns.tolist()])
    table_widget.setHorizontalHeaderLabels(headers)
    
    # Set header alignment
    header = table_widget.horizontalHeader()
    header.setDefaultAlignment(header_alignment)
    
    # Populate table with data
    for row in range(n_rows):
        # Add index if requested
        if display_index:
            index_item = QtWidgets.QTableWidgetItem(str(df.index[row]))
            index_item.setFlags(index_item.flags() ^ QtCore.Qt.ItemIsEditable)
            table_widget.setItem(row, 0, index_item)
            col_offset = 1
        else:
            col_offset = 0
        
        # Add data cells
        for col in range(n_cols):
            value = df.iloc[row, col]
            item = QtWidgets.QTableWidgetItem(str(value) if not pd.isna(value) else "")
            item.setTextAlignment(data_alignment)
            
            # Make cells non-editable
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
            
            table_widget.setItem(row, col + col_offset, item)
    
    # Stretch columns if requested
    if stretch_columns:
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
    else:
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
    
    # Enable alternating row colors
    if alternate_row_colors:
        table_widget.setAlternatingRowColors(True)
    
    # Resize rows to content
    table_widget.resizeRowsToContents()

###############################################################
###############################################################
###############################################################     QT objects
###############################################################
###############################################################

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
        self.db_name_line.setText("База данных")
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
        self.on_file_input()
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
            """Adds new table column toggle"""

            # Index for new row
            cur_row = self.table.rowCount()
            self.table.setRowCount(cur_row+1)

            # SQL column name (editable, defaults to Excel name)
            sql_item = QtWidgets.QTableWidgetItem("Название столбца")
            self.table.setItem(cur_row, 0, sql_item)
        self.add_column_button.clicked.connect(on_add_column)
        self.add_column.addWidget(self.add_column_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.add_column.addItem(spacerItem)
        self.verticalLayout.addLayout(self.add_column)
        self.table = QtWidgets.QTableWidget(Create_db)
        self.table.setObjectName("table")
        self.table.setColumnCount(1)
        self.table.setRowCount(2)
        self.table.setHorizontalHeaderLabels(["Название"])
        self.table.horizontalHeader().setStretchLastSection(True)
        item1=QtWidgets.QTableWidgetItem("Поставщик")
        item1.setFlags(item1.flags() & ~QtCore.Qt.ItemIsEditable)
        item2=QtWidgets.QTableWidgetItem("Артикул")
        item2.setFlags(item2.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(0,0,item1)
        self.table.setItem(1,0,item2)
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
        if not self.createPrice(path):
            return
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
    
    def createPrice(self, path: str) -> bool:
        """
            Accessed only through self.create_db
        """

        prices = {'Индекс' : "INTEGER PRIMARY KEY AUTOINCREMENT",
                  'Название': "TEXT NOT NULL UNIQUE",
                  'Путь': "TEXT NOT NULL UNIQUE"}
        
        if not createTable(self.dialog_window, path, "СПИСОК ПОСТАВЩИКОВ", prices):
            return False
        insert = []
        for row in range(self.table.rowCount()):
            insert.append(self.table.item(row, 0).text())
        try:
            querry = f"""CREATE VIRTUAL TABLE "ПРАЙС" USING FTS5({",".join(insert)})"""
            with sqlite3.connect(path) as conn:
                conn.execute(querry)
        except Exception as ex:
            throw_exeption(self.dialog_window, f'Error occured: {ex}')
            return False
        return True

    def retranslateUi(self, Create_db):
        _translate = QtCore.QCoreApplication.translate
        Create_db.setWindowTitle(_translate("Create_db", "Dialog"))
        self.db_name_lable.setText(_translate("Create_db", "Название базы даных:"))
        self.file_input_lable.setText(_translate("Create_db", "Расположение файла:"))
        self.file_input_button.setText(_translate("Create_db", "..."))
        self.label.setText(_translate("Create_db", "Добавить столбцы: "))
        self.add_column_button.setToolTip(_translate("Create_db", "Добавить столбец"))
        self.add_column_button.setText(_translate("Create_db", "Добавить"))

class Ui_Add_table_dialog(object):
    
    def setupUi(self, Add_table_dialog: QtWidgets.QDialog, parent):
        Add_table_dialog.setObjectName("Add_table_dialog")
        Add_table_dialog.resize(765, 586)
        self.parent = parent
        self.add_table_window = Add_table_dialog
        self.verticalLayout = QtWidgets.QVBoxLayout(Add_table_dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.table_name = QtWidgets.QHBoxLayout()
        self.table_name.setObjectName("table_name")
        self.table_name_lable = QtWidgets.QLabel(Add_table_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.table_name_lable.sizePolicy().hasHeightForWidth())
        self.table_name_lable.setSizePolicy(sizePolicy)
        self.table_name_lable.setMaximumSize(QtCore.QSize(180, 100))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.table_name_lable.setFont(font)
        self.table_name_lable.setToolTip("")
        self.table_name_lable.setObjectName("table_name_lable")
        self.table_name.addWidget(self.table_name_lable)
        self.table_name_line = QtWidgets.QLineEdit(Add_table_dialog)
        self.table_name_line.setObjectName("table_name_line")
        self.table_name.addWidget(self.table_name_line)
        self.verticalLayout.addLayout(self.table_name)
        self.file_input = QtWidgets.QHBoxLayout()
        self.file_input.setObjectName("file_input")
        self.file_input_lable = QtWidgets.QLabel(Add_table_dialog)
        self.file_input_lable.setMaximumSize(QtCore.QSize(180, 16777215))
        font = QtGui.QFont()
        font.setPointSize(10)
        def on_file_input():
            file, check = QtWidgets.QFileDialog.getOpenFileName(
                                self.add_table_window,
                                "Загрузка поставщика",
                                "C:\\",
                                self.add_table_window.tr(
                                    'Файл для загрузки (*.xlsx *.xls);;'))
            if check:
                self.file_input_line.setText(file)
                d_frame = pd.read_excel(self.file_input_line.text())
                selectables = ['НЕ НАЗНАЧЕНО']
                selectables.extend([f'{i}' for i in d_frame.columns])
                columns = get_table_columns(self.parent.path, "ПРАЙС")
                print(columns)
                for column in columns[1:]:
                    self.add_item(column, selectables)
                try:
                    self.table_name_line.setText(findall(r"([^/]+?)\.xlsx?$",self.file_input_line.text())[0])
                except Exception as ex:
                    throw_exeption(self.add_table_window, f"Error occured: {ex}")
        self.file_input_lable.setFont(font)
        self.file_input_lable.setObjectName("file_input_lable")
        self.file_input.addWidget(self.file_input_lable)
        self.file_input_line = QtWidgets.QLineEdit(Add_table_dialog)
        self.file_input_line.setEnabled(False)
        self.file_input_line.setObjectName("file_input_line")
        self.file_input.addWidget(self.file_input_line)
        self.file_input_button = QtWidgets.QPushButton(Add_table_dialog)
        self.file_input_button.setMaximumSize(QtCore.QSize(50, 16777215))
        self.file_input_button.setObjectName("file_input_button")
        self.file_input.addWidget(self.file_input_button)
        self.file_input_button.clicked.connect(on_file_input)
        self.verticalLayout.addLayout(self.file_input)
        self.table = QtWidgets.QTableWidget(Add_table_dialog)
        self.table.setObjectName("table")
        self.table.setColumnCount(2)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels(["В базе", "У поставщика"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.verticalLayout.addWidget(self.table)
        self.dialog_button = QtWidgets.QDialogButtonBox(Add_table_dialog)
        self.dialog_button.setOrientation(QtCore.Qt.Horizontal)
        self.dialog_button.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.dialog_button.setObjectName("dialog_button")
        self.verticalLayout.addWidget(self.dialog_button)
        self.dialog_button.rejected.connect(self.add_table_window.close)
        self.dialog_button.accepted.connect(self.on_add_table)

        on_file_input()
        self.retranslateUi(Add_table_dialog)
        QtCore.QMetaObject.connectSlotsByName(Add_table_dialog)

    def retranslateUi(self, Add_table_dialog):
        _translate = QtCore.QCoreApplication.translate
        Add_table_dialog.setWindowTitle(_translate("Add_table_dialog", "Добавить поставщика"))
        self.table_name_lable.setText(_translate("Add_table_dialog", "Название поставщика:"))
        self.file_input_lable.setText(_translate("Add_table_dialog", "Расположение файла:"))
        self.file_input_button.setText(_translate("Add_table_dialog", "..."))

    def on_add_table(self):
        if self.file_input_line == '':
            return
        if self.table_name_line == '':
            return
        sql_table = {"НАЗВАНИЕ В БД":"TEXT PRIMARY KEY",
                    "НАЗВАНИЕ У ПОСТАВЩИКА":"TEXT"}
        if not createTable(self.add_table_window, self.parent.path, self.table_name_line.text(), sql_table):
            return
        insert_into_table(self.add_table_window, self.parent.path, "СПИСОК ПОСТАВЩИКОВ", ["Название", "Путь"], [[self.table_name_line.text(), self.file_input_line.text()]])
        insert = []
        for row in range(self.table.rowCount()):
            insert.append([self.table.item(row,0).text(),self.table.cellWidget(row,1).currentText()])
        
        insert_into_table(self.add_table_window, self.parent.path, self.table_name_line.text(), list(sql_table.keys()), insert)
        
        self.parent.on_update_price([[self.table_name_line.text(), self.file_input_line.text()]])
        self.add_table_window.close()
  
    def add_item(self, column, selectables):
        cur_row = self.table.rowCount()
        self.table.setRowCount(cur_row+1)
        sql_item = QtWidgets.QTableWidgetItem(column)
        sql_item.setFlags(sql_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(cur_row, 0, sql_item)

        # Columns combo box
        combo = QtWidgets.QComboBox()
        combo.addItems(selectables)
        
        self.table.setCellWidget(cur_row, 1, combo)

class Ui_OpenerSearchPrice(object):
    def on_update_price(self, tables: List[List[str]] = None):
        if tables == None:
            tables = [[j for j in list(i)[1:]] for i in get_table_data(self.MainWindow, self.path, "СПИСОК ПОСТАВЩИКОВ")]
        for table in tables:
            columns = get_table_data(self.MainWindow, self.path, table[0], return_type="dataframe")
            sql_columns = ["Поставщик"]
            excel_columns = []
            for id, column in columns.iterrows():
                sql_columns.append(column[0])
                excel_columns.append(column[1])
            df = pd.read_excel(table[1])[excel_columns]
            values = [row.tolist() for id,row in df.iterrows()]
            for i in range(len(values)):
                buf = [table[0]]
                buf.extend(values[i])
                values[i]=buf
            with sqlite3.connect(self.path) as conn:
                query = f"DELETE  FROM \"ПРАЙС\" WHERE \"Название\"=\'{table[1]}\'"
                conn.cursor().execute(query)
            insert_into_table(self.MainWindow, self.path, "ПРАЙС", 
                              sql_columns, values)
        self.tableWidget.clearContents()
        result = get_table_data(self.MainWindow, self.path, "ПРАЙС", limit=50, return_type="dataframe")
        dataframe_to_qtablewidget(result, self.tableWidget)

    def on_create_db(self):
        create_db_window = QtWidgets.QDialog(self.MainWindow)
        create_db = Ui_Create_db()
        create_db.setupUi(create_db_window, self)
        create_db_window.show()

    def on_add_table(self):
        create_table_window = QtWidgets.QDialog(self.MainWindow)
        create_table = Ui_Add_table_dialog()
        create_table.setupUi(create_table_window, self)
        create_table_window.show()

    def on_search(self):
        requests = []
        for i in self.verticalLayout_2.children():
            requests.extend(i.itemAt(1).widget().text().split())
        try:
            with sqlite3.connect(self.path) as conn:
                querry = f'''SELECT * FROM "ПРАЙС" WHERE "ПРАЙС" MATCH '{"* OR ".join(requests)}*' ORDER BY rank '''
                conn.cursor().execute(querry)
                df = pd.read_sql_query(querry, conn)
                dataframe_to_qtablewidget(pd.DataFrame(df), self.tableWidget)
        except Exception as ex:
            throw_exeption(self.MainWindow, f"Error occured: {ex}")

    def set_opened_stage(self):
        self.centralwidget.close()
        self.centralwidget = QtWidgets.QWidget(SearchPrice)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setContentsMargins(20, 20, 20, 10)
        self.verticalLayout.setObjectName("verticalLayout")
        self.searchArea = QtWidgets.QScrollArea(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.searchArea.sizePolicy().hasHeightForWidth())
        self.searchArea.setSizePolicy(sizePolicy)
        self.searchArea.setMinimumSize(QtCore.QSize(0, 50))
        self.searchArea.setWidgetResizable(True)
        self.searchArea.setObjectName("searchArea")
        self.searchAreaContents = QtWidgets.QWidget()
        self.searchAreaContents.setGeometry(QtCore.QRect(0, 0, 955, 198))
        self.searchAreaContents.setObjectName("searchAreaContents")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.searchAreaContents)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        spacerItem1 = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem1)
        self.searchArea.setWidget(self.searchAreaContents)
        self.verticalLayout.addWidget(self.searchArea)
        self.search_pannel = QtWidgets.QHBoxLayout()
        self.search_pannel.setObjectName("search_pannel")
        spacerItem2 = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.search_pannel.addItem(spacerItem2)
        self.search_pannel_button = QtWidgets.QPushButton(self.searchAreaContents)
        self.search_pannel_button.setObjectName("search_pannel_button")
        self.search_pannel_button.clicked.connect(self.on_search)
        self.search_pannel.addWidget(self.search_pannel_button)
        self.verticalLayout.addLayout(self.search_pannel)
        self.tableWidget = QtWidgets.QTableWidget(self.centralwidget)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(0)
        self.tableWidget.setRowCount(0)
        self.verticalLayout.addWidget(self.tableWidget)
        SearchPrice.setCentralWidget(self.centralwidget)
        self.add_searchpoint("Поиск")

        _translate = QtCore.QCoreApplication.translate
        self.search_pannel_button.setText(_translate("SearchPrice", "Поиск"))

    def add_searchpoint(self, searchpoint):
        _translate = QtCore.QCoreApplication.translate
        search_item_example = QtWidgets.QHBoxLayout()
        search_item_example.setObjectName("search_item_example")
        label_example = QtWidgets.QLabel(self.searchAreaContents)
        label_example.setObjectName("label_example")
        label_example.setText(_translate("SearchPrice", f"{searchpoint}:"))
        search_item_example.addWidget(label_example)
        lineEdit_example = QtWidgets.QLineEdit(self.searchAreaContents)
        lineEdit_example.setObjectName("lineEdit_example")
        lineEdit_example.setMinimumWidth(200)
        search_item_example.addWidget(lineEdit_example)
        spacerItem = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        search_item_example.addItem(spacerItem)
        self.verticalLayout_2.insertLayout(self.verticalLayout_2.count()-1, search_item_example)

    def on_open_db(self):
        if self.path == None or not self.path[-3:] == ".db":
            file, check = QtWidgets.QFileDialog.getOpenFileName(
            self.MainWindow,
            "QFileDialog.getOpenFileName()",
            "C:\\",
            self.MainWindow.tr(
                'Файл базы данных (*.db);;'))
            if check:
                self.path = file
        if self.path == None: return
        self.set_opened_stage()
        dframe = get_table_data(self.MainWindow, self.path, "ПРАЙС", return_type="dataframe", limit=500)
        dataframe_to_qtablewidget(dframe, self.tableWidget)
        self.table.setEnabled(True)
        self.price.setEnabled(True)
        self.price_update.setEnabled(True)  

    def setupUi(self, OpenerSearchPrice):
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
        self.price_update.setObjectName("price_update")
        self.price_update.setEnabled(False)
        self.price_update.triggered.connect(lambda : self.on_update_price())
        self.price_reconfigure = QtWidgets.QAction(OpenerSearchPrice)
        self.price_reconfigure.setObjectName("price_reconfigure")
        self.price_reconfigure.setEnabled(False)
        self.table_add = QtWidgets.QAction(OpenerSearchPrice)
        self.table_add.setObjectName("table_add")
        self.table_add.triggered.connect(self.on_add_table)
        self.table_reconfigure = QtWidgets.QAction(OpenerSearchPrice)
        self.table_reconfigure.setObjectName("table_reconfigure")
        self.table_reconfigure.setEnabled(False)
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
        self.table.setTitle(_translate("OpenerSearchPrice", "Поставщик"))
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

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    SearchPrice = QtWidgets.QMainWindow()
    ui = Ui_OpenerSearchPrice()
    SearchPrice.setObjectName("OpenerSearchPrice")
    SearchPrice.resize(2000, 1000)
    ui.setupUi(SearchPrice)
    SearchPrice.show()
    sys.exit(app.exec_())
