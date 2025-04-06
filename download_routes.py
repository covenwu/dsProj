import os
import sqlite3
import csv
from flask import Blueprint, send_file, make_response
from io import StringIO

download_bp = Blueprint('download', __name__)

@download_bp.route('/download/socrate')
def download_socrate():
    """Generate and download a CSV file from chat_history.db"""
    try:
        # Connect to the database
        conn = sqlite3.connect('chat_history.db')
        cursor = conn.cursor()
        
        # Query all data from the database
        cursor.execute('''
            SELECT * FROM conversations
        ''')
        
        data = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Create a string buffer and csv writer
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(column_names)
        
        # Write data rows
        writer.writerows(data)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=socrate_chat_history.csv'
        response.headers['Content-type'] = 'text/csv'
        
        # Close connection
        conn.close()
        
        return response
    
    except Exception as e:
        return str(e), 500

@download_bp.route('/download/thinkaloud')
def download_thinkaloud():
    """Generate and download a CSV file from chat_history1.db"""
    try:
        # Connect to the database
        conn = sqlite3.connect('chat_history1.db')
        cursor = conn.cursor()
        
        # Query all data from the database
        cursor.execute('''
            SELECT * FROM conversations
        ''')
        
        data = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Create a string buffer and csv writer
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(column_names)
        
        # Write data rows
        writer.writerows(data)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=thinkaloud_chat_history.csv'
        response.headers['Content-type'] = 'text/csv'
        
        # Close connection
        conn.close()
        
        return response
    
    except Exception as e:
        return str(e), 500 