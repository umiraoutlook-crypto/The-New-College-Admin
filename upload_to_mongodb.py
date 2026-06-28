import csv
from pymongo import MongoClient
import os
import pandas as pd

# MongoDB Atlas connection string
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://umiraoutlook_db_user:umira123@cluster0.x4b4h0j.mongodb.net/?appName=Cluster0')

# Database and collection names
DB_NAME = 'mcq_system'
COLLECTION_NAME = 'student'

def upload_csv_to_mongodb(csv_file_path):
    """
    Upload CSV data to MongoDB Atlas student collection
    """
    try:
        # Connect to MongoDB Atlas
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        print(f"Connected to MongoDB Atlas")
        print(f"Database: {DB_NAME}")
        print(f"Collection: {COLLECTION_NAME}")
        
        # Read CSV file using pandas
        if not os.path.exists(csv_file_path):
            print(f"Error: File not found: {csv_file_path}")
            print(f"Current directory: {os.getcwd()}")
            return
        
        print(f"Reading file: {csv_file_path}")
        
        # Read CSV with pandas to handle formatting better
        df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
        
        # Convert to list of dictionaries
        students = []
        for _, row in df.iterrows():
            if pd.notna(row.get('register_number')) and str(row['register_number']).strip() != '':
                student = {
                    'register_number': str(row['register_number']).strip(),
                    'name': str(row['name']).strip() if pd.notna(row.get('name')) else '',
                    'dob': str(row['dob']).strip() if pd.notna(row.get('dob')) else '',
                    'dob_display': str(row['dob_display']).strip() if pd.notna(row.get('dob_display')) else '',
                    'programme': str(row['programme']).strip() if pd.notna(row.get('programme')) else '',
                    'admission_year': str(row['admission_year']).strip() if pd.notna(row.get('admission_year')) else ''
                }
                students.append(student)
        
        print(f"Read {len(students)} students from CSV")
        
        # Insert data into MongoDB
        if students:
            result = collection.insert_many(students)
            print(f"Successfully inserted {len(result.inserted_ids)} documents into {COLLECTION_NAME} collection")
        else:
            print("No data to insert")
        
        client.close()
        print("Upload completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    csv_path = 'data.csv'
    upload_csv_to_mongodb(csv_path)
