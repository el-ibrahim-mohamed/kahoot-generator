# Step 1: Importing necessary libraries
import streamlit as st
from google import genai
import tempfile
import json
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from serpapi import GoogleSearch
import requests
from PIL import Image
import io
import traceback
import time

# Step 2: Configuring the Streamlit app
st.set_page_config(
    page_title="Kahoot Quiz Generator",
    page_icon="🤖",
)

# Step 3: Title
st.title(":blue[🤖 AI Kahoot Quiz Generator]")
st.write("**Built for Frau Nayeer**")

# Step 4: Taking the quiz data inputs
"---"
st.header("Let's create your Kahoot Quiz! 🎉")

# Metadata
" "
title = st.text_input("Title", placeholder="Enter a title for your kahoot.", max_chars=95)

description = st.text_area("Description (Optional)", placeholder="Provide a short description for your kahoot to increase visibility.", max_chars=500, height=100)


# Source Files
"---"
take_text = st.multiselect("Select the source type", ["Auto Generate", "PDF File", "Plain Text"])

main_topic = None
source_pdfs = []
source_text = None

if "Auto Generate" in take_text:
    main_topic = st.text_input("Auto Generate", placeholder="Type The Main Topic(s)", value=title)

if "PDF File" in take_text:
    source_pdfs = st.file_uploader("Upload Your Sources as PDF", type=["pdf"], accept_multiple_files=True)

if "Plain Text" in take_text:
    source_text = st.text_area("Plain Text", placeholder="Paste your text here", height=200)


# Number of Questions
"---"
questions_num = st.number_input("Number of Questions", min_value=1, max_value=100, value=20, step=5)


# Language
gemini_supported_languages = [
    "Arabic", "Bengali", "Bulgarian",
    "Chinese (simplified)", "Chinese (traditional)",
    "Croatian", "Czech", "Danish",
    "Dutch", "English", "Estonian",
    "Finnish", "French", "German",
    "Greek", "Hebrew", "Hindi",
    "Hungarian", "Indonesian", "Italian",
    "Japanese", "Korean", "Latvian",
    "Lithuanian", "Norwegian", "Polish",
    "Portuguese", "Romanian", "Russian",
    "Serbian", "Slovak", "Slovenian",
    "Spanish", "Swahili", "Swedish",
    "Thai", "Turkish", "Ukrainian",
    "Vietnamese"
]

" "
language = st.selectbox("Language", gemini_supported_languages, index=gemini_supported_languages.index("English"))

# Custom Prompt
"---"
custom_hint = """Make all the questions in German, no English. 
- 5 questions about the vocab with images like: Was ist das and Wie heißt dieses Spielzeug?
- 6 about the conjunctions of the 4 modal past verbs no images
- 4 questions about Grammatik 'Dass-Satz' no images like is this sentence correct (play around the H.S and N.S)
- one fill in the blank with the options (dass, wenn, weil, und).

Strict Notes:
- You must randomize the questions' orders, for example, not all the first 5 questions after each other.
- Don't make repeated questions (ideas).
- The student's level is considered beginner in German, so don't include hard words in the question.
- Don't include exact sentences from the PDF, change them but with the same idea."""

hints = [
    ["German Kahoot", "Make all the questions in German, no English. Don't make images in every single question"],
    ["Built For Frau Nayeer", custom_hint],
]

hint = st.pills("Hints", [hint[0] for hint in hints])

custom_prompt_value = ""
if hint:
    custom_prompt_value = [hint_list[1] for hint_list in hints if hint == hint_list[0]][0]

custom_prompt = st.text_area("Custom Prompt (Optional)", placeholder="Provide custom instructions to guide the AI model. It's recommended to provide what question ideas you want.", height=200, value=custom_prompt_value)


# Step 5: Generate the Kahoot Quiz Data By Gemini

if "quiz_inputs" not in st.session_state:
    st.session_state.quiz_inputs = []
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "create_kahoot_clicked" not in st.session_state:
    st.session_state.create_kahoot_clicked = False
if "result_link" not in st.session_state:
    st.session_state.result_link = None

def generate_quiz_data(
    title: str,
    language: str,
    questions_num: int,
    pdfs_bytes: list = [],
    source_text: str = None,
    topic: str = None,
    description: str = None,
    custom_prompt: str = None,
):
    """
    Generates quiz data from multiple PDF files
    Args:
        title (str): Quiz title
        language (str): Language of the quiz
        questions_num (int): Number of questions in the quiz
        pdfs_bytes (list): List of PDF files
        source_text (str): Source text for the quiz
        topic (str): Topic for the quiz
        description (str): Description for the quiz
        custom_prompt (str): Custom prompt for the AI model
    Returns:
        str: Model output (quiz data in JSON format)
    """

    # Configuring Gemini API with the API key
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Uploading source files with the File API
    with st.spinner("Analyzing your sources..."):
        uploaded_files = []

        for pdf_bytes in pdfs_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                temp_path = tmp.name

            uploaded_file = client.files.upload(file=temp_path, config={"display_name": "Source PDF"})
            uploaded_files.append(uploaded_file)

    # Creating the prompt
    prompt = f"""
Generate quiz data which includes questions, choices, answers and images based on the given sources.
Quiz Title: {title}
{f"Description: {description}" if description else ""}
Language: {language}. All questions and choices should be in this language.
Number of Questions: {questions_num}
{f"Source Text: {source_text}" if source_text else ""}
{f"Topic: {topic}" if topic else ""}{f". Generate the quiz data based on it." if not source_text and not pdfs_bytes else ""}
You should return the output in JSON format with no extra text, in this exact structure:
{{
    "questions": [
        {{
            "type": "multiple_choice / true_or_false", (These are the only 2 options)
            "question": "Question 1",
            "choices": ["Choice 1", "Choice 2", "Choice 3", "Choice 4"],
            "answer": 0 (the index of the correct choice),
            "image": "image description here" (Only if the image is needed as part of the question or refrence to it else set it to null + The image should not reveal the answer)
        }},
        {{
            "type": "multiple_choice / true_or_false",
            "question": "Question 2",
            "choices": ["Choice 1", "Choice 2"] (2 choices if true or false question, 4 choices if multiple choice question),
            "answer": 1,
            "image": "a google image friendly search keyword" (Make it Google-Images-friendly keyword, short and desciptive. Only if the image is needed as part or refrence for the question else set it to null)
        }}
    ],
    "cover_image": "image description here"
}}
Notes:
1. You don't have to put images in all question. Only add images when the questions needs it, not for decoration or visualization.
{f"Here is a custom prompt for instructions from the user: {custom_prompt}" if custom_prompt else ""}
"""
    # Generating the quiz data
    with st.spinner("Generating your quiz questions..."):
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt, *uploaded_files],
            config={
                "response_mime_type": "application/json"
            },
        )

    quiz_data = response.text
    quiz_data = quiz_data.replace("```json", "")
    quiz_data = json.loads(quiz_data)

    # Always setting the type of Q1 to Multiple Choice to avoid errors in Kahoot
    quiz_data["questions"][0]["type"] = "multiple_choice"

    return quiz_data


def create_kahoot_quiz(quiz_data: dict, kahoot_email: str, kahoot_password: str):

    # Step 1: Defining Utility Functions
    def wait_and_click(driver, by, locator, timeout=15):
        """Wait until element is clickable and then click it."""
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, locator))
        )

        element.click()

        return element


    def wait_and_send_keys(driver, by, locator, text, timeout=15):
        """Wait until element is present and send keys."""
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, locator))
        )
        element.send_keys(text)
        return element
    

    def safe_wait_and_click(driver, by, locator, timeout=15, retries=3):
        """Click with retry if element gets stale."""
        for attempt in range(retries):
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, locator))
                )
                element.click()
                return element
            except StaleElementReferenceException:
                if attempt == retries - 1:
                    raise
                time.sleep(0.5)  # brief pause before retry
    

    SERPAPI_API_KEY = st.secrets["SERPAPI_API_KEY"]

    def get_image(query: str):
        params = {
        "engine": "google_images",
        "q": query,
        "api_key": SERPAPI_API_KEY
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        for i in range(len(results["images_results"])):
            try:
                image_url = results["images_results"][i]["original"] 
                response = requests.get(image_url)
                response.raise_for_status()

                img_bytes = response.content
                break

            except:
                pass
        
        # Convert image to proper JPEG
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            image.save(tmp, format="JPEG")
            temp_path = tmp.name

        return temp_path
    

    # Step 2: Setting up the Selenium WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.maximize_window()


    # Step 3: Navigating to Kahoot Login Page and Logging In
    driver.get("https://create.kahoot.it/auth/login")

    # Reject cookies if popup appears
    try:
        wait_and_click(driver, By.ID, "onetrust-reject-all-handler", timeout=5)
    except:
        pass

    # Fill login form
    wait_and_send_keys(driver, By.ID, "username", kahoot_email)
    wait_and_send_keys(driver, By.ID, "password", kahoot_password)
    wait_and_click(driver, By.ID, "login-submit-btn")

    try:
        error_span = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.error-message__ErrorMessageComponent-sc-sut6rh-0"))
        )
        return False, "Invalid username, email, or password."
    
    except TimeoutException:
        pass


    # Step 4: Creating a New Kahoot

    # Handle subscription popup if exists
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "ipm-frame")))
        driver.refresh()
    except:
        pass
    
    # Clicking the Create Button
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='top-bar__create']")

    # Clicking the Kahoot option
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='top-bar__create-kahoot']")
    
    # Clicking the Blank Canvas option
    wait_and_click(driver, By.XPATH, "//div[text()='Blank canvas']/ancestor::button")


    # Step 5: Filling in the Kahoot Quiz Data
    
    # Step 5.1: Entering the title, description and cover page (metadata)

    # Entering to the settings
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='top-bar__kahoot-summary-button']")

    # Entering the title
    wait_and_send_keys(driver, By.ID, "kahoot-title", quiz_data["title"])

    # Entering the description
    wait_and_send_keys(driver, By.ID, "description", quiz_data["description"])

    # Entering the cover page
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='dialog-information-kahoot__image_library_btn']") # Add Button
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='open-upload-media-dialog-button']") # Upload Media Button

    wait_and_send_keys(driver, By.CSS_SELECTOR, "[data-functional-selector='media-upload-dialog__upload-media-input']", get_image(quiz_data["cover_image"]))

    # Waiting for the image to load
    WebDriverWait(driver, 50).until(
        EC.presence_of_element_located(
            (By.ID, "cover-image")
        )
    )

    # Clicking the Done Button to Submit
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='dialog-information-kahoot__done-button']")


    # Step 5.2: Entering the questions, choices, answers and images.
    for i, question in enumerate(quiz_data["questions"]):
        # Question
        question_box = wait_and_click(driver, By.CSS_SELECTOR, "div[data-functional-selector='question-title__input'][contenteditable='true']")
        question_box.send_keys(question["question"])

        # Image
        if question["image"]:
            wait_and_click(driver, By.CLASS_NAME, "MUmzd") # Clicking the upload file button
            wait_and_send_keys(driver, By.CSS_SELECTOR, "[data-functional-selector='media-upload-dialog__upload-media-input']", get_image(question["image"]))

            # Waiting for the image to load
            WebDriverWait(driver, 50).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "img[data-functional-selector='media-details__media-image']")
                )
            )

        # Choices
        if question["type"].lower() == "multiple_choice":
            for choice, id_idx in zip(question["choices"], range(0, len(question["choices"]))):
                # Entering the answer
                editable_div = wait_and_click(driver, By.ID, f"question-choice-{id_idx}")
                editable_div.send_keys(choice)
        
        # Answer
        answer_index = question["answer"]
        wait_and_click(driver, By.CSS_SELECTOR, f'button[data-functional-selector="question-answer__toggle-button"][aria-label="Toggle answer {answer_index + 1} correct."]')

        # Add Question Button
        if i < len(quiz_data["questions"]) - 1:
            wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='add-question-button']")

            # Choosing the new question's type based on the type of the next question
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.create-block__Section-sc-1rs5jsh-2"))
            )

            next_question_type = quiz_data["questions"][i + 1]["type"].lower()
            if next_question_type == "multiple_choice":
                safe_wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='create-button__quiz']")

            elif next_question_type == "true_or_false":
                safe_wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='create-button__true-false']")


    # Step 6: Saving the Kahoot

    # Clicking Save
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='top-bar__save-button']")

    # Taking the Kahoot share link
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='dialog-complete-kahoot__share_kahoot']") # Clicking Share
    link_elem = driver.find_element(By.ID, "share-kahoot-link")

    # Geting the "value" attribute (contains the link)
    kahoot_link = link_elem.get_attribute("value")
    print(kahoot_link)

    # Clicking Close
    wait_and_click(driver, By.CLASS_NAME, 'styles__1g5agrwi')

    # Clicking Done
    wait_and_click(driver, By.CSS_SELECTOR, "button[data-functional-selector='dialog-complete-kahoot__finish-button']")

    # Quitting the browser
    driver.quit()

    return True, kahoot_link


"---"
if st.session_state.result_link:
    st.balloons()
    st.success("Kahoot created successfully!")
    st.write(f"**Kahoot Link**: {st.session_state.result_link}")
    st.write("**You can also view and edit your Kahoot from your Kahoot account.**")

    if st.button("Create New Kahoot", use_container_width=True):
        st.session_state.quiz_inputs = []
        st.session_state.quiz_data = None
        st.session_state.create_kahoot_clicked = False
        st.session_state.result_link = None
        st.rerun()


elif st.session_state.quiz_inputs:
    title, language, questions_num, pdfs_bytes, source_text, main_topic, description, custom_prompt = st.session_state.quiz_inputs

    try:
        if not st.session_state.quiz_data:
            st.session_state.quiz_data = generate_quiz_data(title, language, questions_num, pdfs_bytes, source_text, main_topic, description, custom_prompt)

    except Exception as e:
        st.error("An error occured while generating the quiz data! Please try again later.")
        st.session_state.quiz_inputs = []
        st.session_state.quiz_data = None
        traceback.print_exc()
        st.rerun()


    # Adding the quiz title, description and time limit to the JSON data
    quiz_data = st.session_state.quiz_data

    quiz_data["title"] = title
    quiz_data["description"] = description

    # Previewing the quiz questions
    st.header("Preview The Kahoot Quiz")
    with st.expander("Preview"):
        letters_list = list(string.ascii_lowercase)
        number_of_questions = len(quiz_data["questions"])

        for i, choice_letter in zip(range(number_of_questions), letters_list):
            st.write(f"**Question {i+1}**: {quiz_data['questions'][i]['question']}")
            " "
            
            for letter, choice in zip(letters_list, quiz_data["questions"][i]["choices"]):
                st.write(f"{letter}. {choice}")

            if not i == number_of_questions - 1:
                "---"
    
    # Step 6: Web Scraping Kahoot to create a kahoot
    col1, col2 = st.columns(2)

    if st.button("Cancel", type="secondary", use_container_width=True):
        st.session_state.quiz_inputs = []
        st.session_state.quiz_data = None
        st.rerun()
        
    if st.button("Create Kahoot", type="primary", use_container_width=True, key="create_kahoot_button") or st.session_state.create_kahoot_clicked:
        st.session_state.create_kahoot_clicked = True
        kahoot_email = st.text_input("Kahoot Email and Username", placeholder="Enter your Kahoot email")
        kahoot_password = st.text_input("Kahoot Password", placeholder="Enter your Kahoot password", type="password")

        st.write("**We value your privacy. Your Kahoot email and password won't be stored on our servers or shared with anyone.**")

        if st.button("Create", type="primary", use_container_width=True, key="create_kahoot_final_button"):

            if kahoot_email and kahoot_password:
                try:
                    with st.spinner("Creating your Kahoot...", show_time=True):
                        success, data = create_kahoot_quiz(quiz_data, kahoot_email, kahoot_password)

                    if success:
                        st.session_state.result_link = data
                        st.rerun()

                    else:
                        st.error(data)
                        st.stop()

                except Exception as e:
                    st.error("An error occured while creating the Kahoot! Please try again later.")
                    st.error(e)
                    st.stop()

            else:
                st.error("Please enter your Kahoot email and password.")


elif st.button("Generate The Kahoot Quiz", type="primary"):
    
    if title:

        if not main_topic and not source_text and not source_pdfs:
            st.error("Please provide at least one source type.")
        
        else:
            # Sanitizing Inputs
            title = title.strip()
            description = description.strip()

            # Generating the quiz data
            pdfs_bytes = []
            if source_pdfs:
                pdfs_bytes = [file.read() for file in source_pdfs]

            st.session_state.quiz_inputs = [title, language, questions_num, pdfs_bytes, source_text, main_topic, description, custom_prompt]
            st.rerun()

    else:
        st.error("Please enter a title for your Kahoot Quiz.")