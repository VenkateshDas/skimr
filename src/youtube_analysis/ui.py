"""UI helper functions for the YouTube Analyzer Streamlit app."""

def get_category_class(category: str) -> str:
    """
    Get the CSS class for a category badge.
    
    Args:
        category: The category name
        
    Returns:
        The CSS class for the category badge
    """
    category = category.lower()
    if "technology" in category:
        return "category-technology"
    elif "business" in category:
        return "category-business"
    elif "education" in category:
        return "category-education"
    elif "health" in category:
        return "category-health"
    elif "science" in category:
        return "category-science"
    elif "finance" in category:
        return "category-finance"
    elif "personal" in category:
        return "category-personal"
    elif "entertainment" in category:
        return "category-entertainment"
    else:
        return "category-other"

def extract_youtube_thumbnail(video_id: str) -> str:
    """
    Get the thumbnail URL for a YouTube video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The URL of the video thumbnail
    """
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def load_css() -> str:
    """
    Load custom CSS for better styling.
    
    Returns:
        The CSS string to be used with st.markdown
    """
    return """
<style>
    /* Global Styles */
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    
    /* Main Styles */
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        color: #FF0000;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #FFFFFF;
        margin: 2rem 0 1rem 0;
        text-align: center;
    }
    .info-text {
        font-size: 1.1rem;
        color: #CCCCCC;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    /* Card Styles */
    .card {
        border-radius: 12px;
        border: none;
        padding: 1.8rem;
        background-color: #1E1E1E;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        margin-bottom: 1.5rem;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 100%;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
    }
    .card h3 {
        font-size: 1.4rem;
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 1rem;
    }
    .card p {
        color: #BBBBBB;
        font-size: 1rem;
        line-height: 1.5;
    }
    .card-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        display: block;
    }
    
    /* Status Indicators */
    .success-box {
        padding: 1rem;
        background-color: rgba(52, 168, 83, 0.15);
        border-radius: 8px;
        border-left: 4px solid #34A853;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    .warning-box {
        padding: 1rem;
        background-color: rgba(249, 168, 37, 0.15);
        border-radius: 8px;
        border-left: 4px solid #F9A825;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    .error-box {
        padding: 1rem;
        background-color: rgba(229, 57, 53, 0.15);
        border-radius: 8px;
        border-left: 4px solid #E53935;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #FF0000;
    }
    
    /* Category Badge */
    .category-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .category-technology {
        background-color: rgba(21, 101, 192, 0.2);
        color: #64B5F6;
    }
    .category-business {
        background-color: rgba(46, 125, 50, 0.2);
        color: #81C784;
    }
    .category-education {
        background-color: rgba(230, 81, 0, 0.2);
        color: #FFB74D;
    }
    .category-health {
        background-color: rgba(123, 31, 162, 0.2);
        color: #CE93D8;
    }
    .category-science {
        background-color: rgba(0, 131, 143, 0.2);
        color: #4DD0E1;
    }
    .category-finance {
        background-color: rgba(57, 73, 171, 0.2);
        color: #9FA8DA;
    }
    .category-personal {
        background-color: rgba(216, 67, 21, 0.2);
        color: #FFAB91;
    }
    .category-entertainment {
        background-color: rgba(130, 119, 23, 0.2);
        color: #DCE775;
    }
    .category-other {
        background-color: rgba(69, 90, 100, 0.2);
        color: #B0BEC5;
    }
    
    /* Metadata */
    .metadata {
        font-size: 0.85rem;
        color: #999999;
        margin-top: 1rem;
        text-align: right;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 8px 8px 0px 0px;
        padding: 0px 16px;
        background-color: #2A2A2A;
        color: #CCCCCC;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FF0000 !important;
        color: white !important;
    }
    
    /* Button styling */
    .stButton button {
        background-color: #FF0000;
        color: white;
        font-weight: 600;
        border-radius: 30px;
        padding: 0.6rem 2rem;
        border: none;
        transition: all 0.3s ease;
        font-size: 1.1rem;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #D50000;
        box-shadow: 0 4px 12px rgba(255, 0, 0, 0.3);
        transform: translateY(-2px);
    }
    
    /* Input field styling */
    .stTextInput input {
        border-radius: 30px;
        border: 2px solid #333333;
        padding: 1rem 1.5rem;
        background-color: #1A1A1A;
        color: #FFFFFF;
        transition: all 0.3s ease;
        font-size: 1.1rem;
    }
    .stTextInput input:focus {
        border-color: #FF0000;
        box-shadow: 0 0 0 2px rgba(255, 0, 0, 0.2);
    }
    .stTextInput input::placeholder {
        color: #777777;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1A1A1A;
        border-right: 1px solid #333333;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #FFFFFF;
    }
    
    /* Text area styling */
    .stTextArea textarea {
        background-color: #1A1A1A;
        color: #CCCCCC;
        border: 1px solid #333333;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #FF0000 #FF0000 transparent !important;
    }
    
    /* Feature grid */
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin: 2rem 0;
    }
    
    /* Step grid */
    .step-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin: 2rem 0;
    }
    
    /* Chat container */
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 60vh;
        overflow-y: auto;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #1A1A1A;
        border-radius: 12px;
        border: 1px solid #333333;
    }
    
    /* Chat message */
    .chat-message {
        display: flex;
        margin-bottom: 1rem;
    }
    
    .chat-message.user {
        justify-content: flex-end;
    }
    
    .chat-message.bot {
        justify-content: flex-start;
    }
    
    .message-content {
        padding: 0.8rem 1.2rem;
        border-radius: 18px;
        max-width: 80%;
        word-wrap: break-word;
    }
    
    .user .message-content {
        background-color: #FF0000;
        color: white;
        border-bottom-right-radius: 4px;
    }
    
    .bot .message-content {
        background-color: #2A2A2A;
        color: white;
        border-bottom-left-radius: 4px;
    }
    
    /* Streamlit chat specific styling */
    [data-testid="stChatMessage"] {
        margin-bottom: 1rem;
    }
    
    /* Make sure the chat input is always visible at the bottom */
    [data-testid="stChatInput"] {
        position: sticky;
        bottom: 0;
        background-color: #121212;
        padding: 1rem 0;
        z-index: 100;
        margin-top: 1rem;
        border-top: 1px solid #333333;
    }
    
    /* Ensure the chat container scrolls properly */
    [data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"]) {
        overflow-y: auto;
        max-height: 60vh;
        padding-right: 1rem;
    }
    
    @media (max-width: 768px) {
        .feature-grid {
            grid-template-columns: 1fr;
        }
        .step-grid {
            grid-template-columns: 1fr 1fr;
        }
    }
</style>
""" 