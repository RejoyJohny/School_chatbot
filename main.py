import pandas as pd
import sqlite3
from google import genai  # <-- FIX 1: Correct import
import os
import re
from datetime import datetime

class SchoolDataChatbot:
    def __init__(self, csv_file_path, api_key):
        """Initialize the chatbot with CSV data and Gemini API"""
        try:
            # --- START OF FIX 2 ---
            
            # The new library uses a Client object
            self.client = genai.Client(api_key=api_key)
            # We just store the model's name to use later
            self.model_name = "models/gemini-flash-latest" 
            
            # (We remove the old 'genai.configure' and 'genai.GenerativeModel' lines)
            print("✅ Gemini AI client initialized successfully!")
            
            # --- END OF FIX 2 ---
            
            # Load school data
            self.df = pd.read_csv(csv_file_path)
            print(f"✅ Loaded school data: {len(self.df)} records")
            
            # Create in-memory database
            self.conn = sqlite3.connect(':memory:')
            
            # Clean column names for SQL
            self.df.columns = [col.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '') for col in self.df.columns]
            self.df.to_sql('schools', self.conn, index=False, if_exists='replace')
            
            # Store column info for prompts
            self.column_info = self._get_column_info()
            
            print("🤖 School Data Chatbot is ready!")
            print(f"📊 Available columns: {list(self.df.columns)}")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            raise
    
    def _get_column_info(self):
        """Get detailed information about each column"""
        column_info = {}
        for col in self.df.columns:
            column_info[col] = {
                'dtype': str(self.df[col].dtype),
                'sample_values': self.df[col].dropna().head(3).tolist(),
                'null_count': self.df[col].isnull().sum(),
                'unique_count': self.df[col].nunique()
            }
        return column_info
    
    def generate_sql_with_ai(self, user_query):
        """Use Gemini to convert natural language to SQL"""
        schema_description = self._create_schema_description()
        
        prompt = f"""
        You are a SQL expert. Convert the following natural language query into SQL for a schools database.
        
        DATABASE SCHEMA:
        Table name: schools
        {schema_description}
        
        QUERY: "{user_query}"
        
        IMPORTANT RULES:
        1. Return ONLY the SQL query, no explanations
        2. Use LIKE for text searches with LOWER() for case-insensitivity
        3. Use appropriate aggregate functions (COUNT, AVG, MAX, MIN) when needed
        4. Always use the actual column names from the schema
        5. Only SELECT queries are allowed
        6. For location searches, check Location, City, State columns
        7. For counts, use COUNT(*) and alias as 'count_result'
        8. For averages, use AVG() and alias appropriately
        
        SQL QUERY:
        """
        
        try:
            # --- START OF FIX 3 ---
            
            # This is the new way to call the API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt  # The prompt now goes into the 'contents' parameter
            )
            
            # --- END OF FIX 3 ---

            sql_query = response.text.strip()
            
            # Clean the response
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            # Security check
            if any(keyword in sql_query.upper() for keyword in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']):
                return "SECURITY_ERROR"
                
            return sql_query
            
        except Exception as e:
            print(f"❌ AI SQL generation failed: {e}")
            return None
    
    def _create_schema_description(self):
        """Create detailed schema description for the AI"""
        description = "Columns:\n"
        for col, info in self.column_info.items():
            description += f"- {col} ({info['dtype']}): Sample values: {info['sample_values']}\n"
        return description
    
    def execute_sql(self, sql_query):
        """Execute SQL query and return results"""
        try:
            result_df = pd.read_sql_query(sql_query, self.conn)
            return result_df
        except Exception as e:
            return f"SQL_EXECUTION_ERROR: {str(e)}"
    
    def generate_chat_response(self, user_query, sql_results, sql_query):
        """Use Gemini to generate a natural language response"""
        if isinstance(sql_results, str):  # Error case
            return f"I encountered an error: {sql_results}"
        
        if len(sql_results) == 0:
            return "I couldn't find any schools matching your criteria. Try different search terms."
        
        # Prepare data for the AI
        if len(sql_results) > 10:
            data_preview = sql_results.head(10).to_dict('records')
            data_info = f"Showing 10 of {len(sql_results)} results: {data_preview}"
        else:
            data_info = f"Results: {sql_results.to_dict('records')}"
        
        prompt = f"""
        You are a helpful school data assistant. The user asked: "{user_query}"
        
        Database returned these results: {data_info}
        
        Please provide a friendly, conversational response that:
        1. Answers the question directly
        2. Summarizes the key findings
        3. Mentions interesting patterns if any
        4. Is concise but informative
        5. Uses emojis to make it engaging
        
        Response:
        """
        
        try:
            # --- START OF FIX 4 ---
            
            # We use the same new client method here
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            # --- END OF FIX 4 ---

            return response.text.strip()
        except Exception as e:
            print(f"❌ AI Chat response generation failed: {e}") # Added for better debugging
            # Fallback response
            return self._create_fallback_response(sql_results, user_query)
    
    def _create_fallback_response(self, results, user_query):
        """Create a fallback response if AI fails"""
        if 'count_result' in results.columns:
            count = results.iloc[0]['count_result']
            return f"📊 I found {count} schools matching your query!"
        
        response = f"🏫 I found {len(results)} schools matching your query:\n\n"
        for i, (_, row) in enumerate(results.head(5).iterrows(), 1):
            # Find school name
            name_cols = [col for col in row.index if 'name' in col.lower() or 'school' in col.lower()]
            school_name = row[name_cols[0]] if name_cols else "Unknown School"
            
            response += f"{i}. **{school_name}**"
            
            # Add location if available
            loc_cols = [col for col in row.index if 'location' in col.lower() or 'city' in col.lower() or 'address' in col.lower()]
            if loc_cols and pd.notna(row[loc_cols[0]]):
                response += f" - {row[loc_cols[0]]}"
            
            response += "\n"
        
        if len(results) > 5:
            response += f"\n... and {len(results) - 5} more schools!"
        
        return response
    
    def get_chatbot_greeting(self):
        """Get a friendly greeting from the chatbot"""
        total_schools = len(self.df)
        
        greetings = [
            f"👋 Hello! I'm your School Data Assistant. I have information about {total_schools:,} schools. How can I help you today?",
            f"🏫 Hi there! I can answer questions about {total_schools:,} schools in our database. What would you like to know?",
            f"📚 Welcome! I have data on {total_schools:,} educational institutions. Ask me anything about schools!",
        ]
        
        return greetings[0]
    
    def process_message(self, user_message):
        """Process a user message and return chatbot response"""
        print(f"👤 User: {user_message}")
        
        # Generate SQL using AI
        sql_query = self.generate_sql_with_ai(user_message)
        
        if sql_query == "SECURITY_ERROR":
            return "❌ I can't execute that type of query for security reasons."
        
        if not sql_query:
            return "🤖 I'm having trouble understanding your query. Could you rephrase it?"
        
        print(f"📝 Generated SQL: {sql_query}")
        
        # Execute the query
        results = self.execute_sql(sql_query)
        
        if isinstance(results, str) and "SQL_EXECUTION_ERROR" in results:
            return "🤖 I had trouble retrieving the data. Could you try asking differently?"
        
        # Generate natural language response
        response = self.generate_chat_response(user_message, results, sql_query)
        
        return response
    
    def show_data_stats(self):
        """Show interesting statistics about the data"""
        stats = {
            "total_schools": len(self.df),
            "columns": list(self.df.columns),
        }
        
        # Add school type distribution if available
        type_cols = [col for col in self.df.columns if 'type' in col.lower()]
        if type_cols:
            stats['school_types'] = self.df[type_cols[0]].value_counts().to_dict()
        
        # Add location stats if available
        location_cols = [col for col in self.df.columns if 'location' in col.lower() or 'city' in col.lower() or 'state' in col.lower()]
        if location_cols:
            stats['top_locations'] = self.df[location_cols[0]].value_counts().head(5).to_dict()
        
        return stats

def main():
    print("🚀 Starting School Data Chatbot...")
    
    # Your configuration
    CSV_FILE = "students.csv"  # Your CSV file
    
    # --- START OF FIX 5 (SECURITY) ---
    # Load your API key safely from an environment variable
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    # --- END OF FIX 5 ---
    
    # Check if files exist
    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV file '{CSV_FILE}' not found!")
        return
    
    # --- START OF FIX 6 (SECURITY) ---
    # Check if the API key was found
    if not GEMINI_API_KEY:
        print("❌ 'GEMINI_API_KEY' environment variable not set.")
        print("💡 Please set this variable in your terminal before running:")
        print("   On Windows: set GEMINI_API_KEY=YOUR_KEY_HERE")
        print("   On macOS/Linux: export GEMINI_API_KEY=YOUR_KEY_HERE")
        return
    # --- END OF FIX 6 ---
    
    try:
        # Initialize chatbot
        chatbot = SchoolDataChatbot(CSV_FILE, GEMINI_API_KEY)
        
        # Show greeting
        print("\n" + "="*60)
        print(chatbot.get_chatbot_greeting())
        print("="*60)
        
        # Show data statistics
        stats = chatbot.show_data_stats()
        print(f"\n📊 Quick stats:")
        print(f"   • Total schools: {stats['total_schools']:,}")
        if 'school_types' in stats:
            print(f"   • School types: {len(stats['school_types'])} different types")
        print(f"   • Available data: {len(stats['columns'])} columns")
        print("\n💡 Try asking questions like:")
        print("   • 'Show me high schools in California'")
        print("   • 'How many colleges are in New York?'")
        print("   • 'Schools with enrollment above 1000'")
        print("   • 'List elementary schools in Texas'")
        print("   • 'Which state has the most schools?'")
        print("\nType 'quit' to exit the chat")
        print("="*60)
        
        # Chat loop
        chat_history = []
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("🤖 Thank you for chatting with me! Have a great day! 👋")
                    break
                
                if not user_input:
                    continue
                
                # Process the message
                print("🤖 Thinking...")
                bot_response = chatbot.process_message(user_input)
                
                # Display response
                print(f"🤖 Bot: {bot_response}")
                
                # Store in history
                chat_history.append({
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'user': user_input,
                    'bot': bot_response
                })
                
            except KeyboardInterrupt:
                print("\n\n🤖 Chat ended by user. Goodbye! 👋")
                break
            except Exception as e:
                print(f"🤖 Oops! Something went wrong: {e}")
                print("🤖 Please try asking your question differently.")
    
    except Exception as e:
        print(f"❌ Failed to start chatbot: {e}")

if __name__ == "__main__":
    main()