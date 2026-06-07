import asyncio 
import sys
import os
import pandas as pd
import streamlit as st
import csv
from pydantic import BaseModel
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from browser_use import Agent, Controller
from dotenv import load_dotenv
from datetime import datetime

# creating a unique name to csv file
def get_unique_csv_filename(base_name='Course', extension='.csv'):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'{base_name}_{timestamp}{extension}'
    return filename

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load environment variables
load_dotenv()

# Check if the key is properly loaded
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the model (Gemini model is correctly set up here)
def set_llm(model: str):
    print(f"LLM requested: {model}")  # Debug log

    if model == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            print("\u274c GEMINI_API_KEY is missing.")
            return None
        return ChatGoogleGenerativeAI(
            model='gemini-2.0-flash-exp',
            api_key=SecretStr(key)
        )

    elif model == "ollama":
        return ChatOllama(model='mistral')

    else:
        print(f"\u274c Unsupported model: {model}")
        return None

# set up Controller
controller = Controller()

# define Course model for structured data saving
class Course(BaseModel):
    code: str
    name: str
    credits: int
    instructor: str
    room: str
    days: str
    start_time: str
    end_time: str
    max_enroll: int
    ttl_enroll: int

# create CSV header
def initialize_csv(filename: str):
    if not filename.endswith('.csv'):
        filename += '.csv'

    if os.path.exists(filename):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{filename[:-4]}_{timestamp}.csv'

    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Course code', 'Course Name', 'Credits', 'Instructors', 'Room', 'Days',
            'Start Time', 'End Time', 'Max Enrollment', 'Total Enrollment'
        ])

    return filename

async def main(user, passw, term, llm_model, csv_filename):
    initial_actions = [
        {"open_tab": {"url": "https://cudportal.cud.ac.ae/student/login.asp"}}
    ]

    sensitive_data = {
        'cudusername': user,
        'cudpassword': passw
    }

    llm = set_llm(llm_model)
    if not llm:
        print("LLM initialization failed.")
        return

    agent = Agent(
        task=( 
            "fill in cudusername and cudpassword\n"
            f"click on change term on the upper left corner and select_dropdown_option: {term} \n"
            "Click 'Show Filter', select 'SEAST' division, and apply the filter.\n"
            "Extract following course details of all courses: Course Code, Name, Credits, Instructor, "
            "Room, Days, Start Time and End Time, Max and Total Enrollment\n"
            f"save extracted data to {csv_filename}.\n"
            "go to next page.\n"
            f"repeat course extraction and save to {csv_filename} until end of pages is reached."
        ),
        llm=llm,
        initial_actions=initial_actions,
        sensitive_data=sensitive_data,
        controller=controller
    )
    
    await agent.run()

def create_save_function(filename):
    @controller.action(f'save extracted data to {csv_filename}', param_model=Course)
    def save_data(c: Course):
        #print(f"Saving data for course: {c.code}")  # Debug log to ensure it's being triggered
        with open(csv_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                c.code, c.name, c.credits, c.instructor, c.room, c.days,
                c.start_time, c.end_time, c.max_enroll, c.ttl_enroll
            ])
    return save_data

# streamlit
st.header('Information Scrapping Tool')
form_values = {
    'Username': None,
    'Password': None,
    'Term': None,
    'CSV_File': None
}

# form to collect the data
with st.form(key='user_input_form'):
    st.write('Please Input your Information.')
    form_values['Username'] = st.text_input('Enter your username: ')
    form_values['Password'] = st.text_input('Enter your password: ', type='password')
    form_values['Term'] = st.text_input('Enter the term (e.g. sp23-24): ')
    form_values['CSV_File'] = st.text_input('Enter desired CSV file name (without extension):')
    form_values['Save_Path'] = st.text_input('Enter full path to save the file (e.g. "C:Program Files/myfile.txt" )')
    form_values['llm_Model'] = st.selectbox('Choose LLM (Language Model):', ['gemini', 'ollama'])

    submit_button = st.form_submit_button('Submit')
    if submit_button:
        if not all(form_values.values()):
            st.warning('Please fill in all the fields.')
        else:
            with st.spinner('Scrapping in progress...'):
                try:
                    # check if the entered path is correct or not
                    if not os.path.isdir(form_values['Save_Path']):
                        st.error('The path you entered does not exist. Please check and try again.')
                        st.stop()

                    full_path = os.path.join(form_values['Save_Path'], form_values['CSV_File'] + '.csv')
                    csv_filename = initialize_csv(full_path)
                    create_save_function(csv_filename)
                    asyncio.run(main(
                        form_values['Username'],
                        form_values['Password'],
                        form_values['Term'],
                        form_values['llm_Model'],
                        csv_filename
                    ))
                    st.success('Scrapping completed successfully')
                    st.divider()
                    st.subheader("Course Query")
                    st.session_state['csv_filename'] = csv_filename
                except Exception as e:
                    st.error(f'An error occurred: {e}')

def csv_data(filename):
    parts = [""]
    with open(filename,"r",newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            str=""
            parts.append(str.join(row))
    return parts

user_prompt = st.text_input("Write the prompt:")
chat_submit = st.button("Submit")
if chat_submit:
    if not user_prompt.strip():
        st.warning("Please enter prompt")
    else:
        try:
            filename = st.session_state.get('csv_filename')
            if filename is None:
                st.warning("CSV filename not set yet.")
            gemini_llm = set_llm("gemini")

            if gemini_llm is None:
                st.error("Error: LLM failed to load. Please check your model name or API key.")

            else:
                gemini_result = gemini_llm.invoke(f"""
                Given the following CSV data:
                {csv_data(filename)}

                Based on the data answer this user prompt clearly and concisely:
                {user_prompt}
                """)

                st.markdown("Answer from Gemini")
                st.write(gemini_result.content)

        except Exception as e:
            st.error(f"Error during CSV-based prompt: {e}")
        st.divider()
olamaa=st.text_input("search under ollama:")
ol = st.button("enter")
if ol:
    if not olamaa.strip():
        st.warning("Please enter prompt")
    else:
        ollama_llm = ChatOllama(model='mistral')
        ollama_result = ollama_llm.invoke(f"{olamaa}")
        st.markdown("Answer from Ollama")
        st.write(ollama_result.content)