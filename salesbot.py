# Import python packages
import _snowflake
import json
import streamlit as st
import time
from snowflake.snowpark.context import get_active_session

# Get the current session
session = get_active_session()

# Page config
st.set_page_config(
    page_title="Sales Data Analysis",
    page_icon=":snowflake:",
    layout="wide",
)

def query_parse_json(json_input, scrape):
    return f"""
    SELECT llm_response:"{scrape}"::STRING AS op FROM (
    SELECT PARSE_JSON('{json_input}') AS llm_response);
    """


def query_gen_rca_cortex(model_name, static_prompt):
    return f"""
    SELECT REPLACE(
    SNOWFLAKE.CORTEX.COMPLETE('{model_name}', '{static_prompt}'
    ), '```', ''
    ) AS query_output;
    """

# Load & cache data
@st.cache_data
def load_data(query_of_interest):
    return session.sql(query_of_interest).to_pandas()
    
# Text2SQL

def send_message(prompt: str):
    database_static_prefix = """
    Instruction: You are an Snowflake SQL expert. Given an input question, first create a syntactically correct Snowflake SQL query and return the query.
    You can order the results to return the most informative data in the database.
    Pay attention to use only the column names you can see in the schema description below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
    Pay attention to use TRUNC(SYSDATE) function to get the current date, if the question involves today.
    Add column aliases.
    Do not add quote for column aliases.
    
    Ensure there are no new lines or inappropriate SQL Keywords in the following json. 
    It has to be a valid json object with output JSON format as below:
    {
        "Instruction": "",
        "Question": "",
        "SQL Query": "",
        "Explanation": "",
        "Note": "",
    }
    
    Remove all other information and return only this VALIDATED JSON object.
    
    Schema Description:
    
    """
    schema_txt = open("schema.txt", "r")
    schema_description = f"{schema_txt.read()}\n"
    static_prompt = database_static_prefix + schema_description + prompt
    if "sess_prompt_output" not in st.session_state:
        st.session_state.sess_prompt_output = ""

    if "sess_query_output" not in st.session_state:
        st.session_state.sess_query_output = ""
    
    st.session_state.sess_prompt_output = (
        load_data(
            query_gen_rca_cortex('mistral-large', static_prompt)
        )["QUERY_OUTPUT"][0]
        .replace("[OUT]","")
        .replace("[/OUT]","")
        .replace("json", "")
        .replace("  ", "")
        .replace("\n", " ")
        .replace("\\n", " ")
        .replace("'", "''")
        .replace("\\_", "_")
        .strip()
    )
    #st.write(st.session_state.sess_prompt_output)
    return load_data(query_parse_json(st.session_state.sess_prompt_output, "SQL Query")
                    )["OP"][0]
       

##########################################################################

def process_message(prompt: str) -> None:
    """Processes a message and adds the response to the chat."""
    st.session_state.messages.append(
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    )
    content=[]
    content.append(
                {"type": "text", "text": prompt}
            )
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Generating response..."):
            sqlstr = send_message(prompt=prompt)
            content.append(
                {"type": "sql", "statement": sqlstr}
            )
            display_content(content=content)
    st.session_state.messages.append({"role": "assistant", "content": content})


def display_content(content: list, message_index: int = None) -> None:
    """Displays a content item for a message."""
    message_index = message_index or len(st.session_state.messages)
    #st.write(content)
    for item in content:
        if item["type"] == "text":
            st.markdown(item["text"])
        elif item["type"] == "sql":
            with st.expander("SQL Query", expanded=False):
                st.code(item["statement"], language="sql")
            with st.expander("Results", expanded=True):
                with st.spinner("Running SQL..."):
                    session = get_active_session()
                    df = session.sql(item["statement"]).to_pandas()
                    st.dataframe(df)
           
st.title("Sales Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []
    
for message_index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        #st.write(message["content"])
        display_content(content=message["content"], message_index=message_index)
        
if user_input := st.chat_input("What is your question?"):
    process_message(prompt=user_input)

##########################################################################
##########################################################################

