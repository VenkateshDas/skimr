from typing import List
from crewai import Agent, Crew, Process, Task, LLM
from crewai.tools import BaseTool
from crewai.project import CrewBase, agent, crew, task
from pydantic import Field
import os

from .utils.logging import get_logger

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_tavily import TavilySearch
logger = get_logger("crew")

search = TavilySearch(max_results=5)

class SearchTool(BaseTool):
    name: str = "Search"
    description: str = "Useful for search-based queries. Use this to find current information about topics, concepts, companies, trends etc."
    search: TavilySearch = Field(default_factory=TavilySearch)

    def _run(self, query: str) -> str:
        try:
            return self.search.invoke(query)
        except Exception as e:
            logger.error(f"Error while searching in Tavily: {e}")
            return f"Error while searching in Tavily: {e}"


@CrewBase
class YouTubeAnalysisCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self, model_name="gpt-4o-mini", temperature=0.2):
        logger.info(f"Initializing YouTubeAnalysisCrew with model: {model_name}, temperature: {temperature}")
        if model_name.startswith("gpt"):
            self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        elif model_name.startswith("claude"):
            anthropic_model = f"anthropic/{model_name}"
            self.llm = LLM(model=anthropic_model, temperature=temperature, api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif model_name.startswith("gemini"):
            # Format the model name to include the 'gemini/' prefix for LiteLLM
            gemini_model = f"gemini/{model_name}"
            self.llm = LLM(model=gemini_model, temperature=temperature, api_key=os.getenv("GEMINI_API_KEY"))

    @agent
    def classifier_agent(self) -> Agent:
        logger.debug("Creating classifier agent")
        return Agent(
            config=self.agents_config['classifier_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def classify_and_summarize_content(self) -> Task:
        """
        Creates a task to classify and summarize the YouTube video based on its transcript.
        
        Returns:
            Task: A CrewAI task for classifying and summarizing the video.
        """
        logger.info("Creating classify and summarize content task")
        return Task(
            config=self.tasks_config['classify_and_summarize_content'],
            agent=self.classifier_agent(),
            async_execution=False
        )
    
    @agent
    def analyzer_agent(self) -> Agent:
        logger.debug("Creating analyzer agent")
        return Agent(
            config=self.agents_config['analyzer_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def analyze_and_plan_content(self) -> Task:
        """
        Creates a task to analyze the video content and create an action plan based on its transcription and summary.
        
        Returns:
            Task: A CrewAI task for analyzing the content and creating an action plan.
        """
        logger.info("Creating analyze and plan content task")
        return Task(
            config=self.tasks_config['analyze_and_plan_content'],
            agent=self.analyzer_agent(),
            async_execution=False
        )
    
    @agent
    def blog_writer_agent(self) -> Agent:
        logger.debug("Creating blog writer agent")
        return Agent(
            config=self.agents_config['blog_writer_agent'],
            verbose=True,
            llm=self.llm,
            tools=[SearchTool()]
        )
    
    @task
    def write_blog_post(self) -> Task:
        """
        Creates a task to write a comprehensive blog post based on the video content.
        
        Returns:
            Task: A CrewAI task for writing a blog post.
        """
        logger.info("Creating write blog post task")
        return Task(
            config=self.tasks_config['write_blog_post'],
            agent=self.blog_writer_agent(),
            context=[self.classify_and_summarize_content(), self.analyze_and_plan_content()]
        )
    
    @agent
    def linkedin_post_writer_agent(self) -> Agent:
        logger.debug("Creating LinkedIn post writer agent")
        return Agent(
            config=self.agents_config['linkedin_post_writer_agent'],
            verbose=True,
            llm=self.llm,
            tools=[SearchTool()]
        )
    
    @task
    def write_linkedin_post(self) -> Task:
        """
        Creates a task to write a professional LinkedIn post based on the video content.
        
        Returns:
            Task: A CrewAI task for writing a LinkedIn post.
        """
        logger.info("Creating write LinkedIn post task")
        return Task(
            config=self.tasks_config['write_linkedin_post'],
            agent=self.linkedin_post_writer_agent(),
            context=[self.classify_and_summarize_content(), self.analyze_and_plan_content()]
        )
    
    @agent
    def tweet_writer_agent(self) -> Agent:
        logger.debug("Creating tweet writer agent")
        return Agent(
            config=self.agents_config['tweet_writer_agent'],
            verbose=True,
            llm=self.llm,
            tools=[SearchTool()]
        )
    
    @task
    def write_tweet(self) -> Task:
        """
        Creates a task to write an engaging tweet based on the video content.
        
        Returns:
            Task: A CrewAI task for writing a tweet.
        """
        logger.info("Creating write tweet task")
        return Task(
            config=self.tasks_config['write_tweet'],
            agent=self.tweet_writer_agent(),
            context=[self.classify_and_summarize_content(), self.analyze_and_plan_content()]
        )
    
    @crew
    def crew(self, analysis_types: List[str] = None) -> Crew:
        """
        Create a CrewAI Crew for YouTube analysis.
        
        Args:
            analysis_types: List of analysis types to generate (default: all types)
        
        Returns:
            Crew: A CrewAI Crew instance configured for YouTube analysis.
        """
        logger.info("Creating YouTube Analysis Crew")
        try:
            if analysis_types is not None and isinstance(analysis_types, tuple):
                analysis_types = list(analysis_types)     
            logger.info(f"Creating crew with selected analysis types: {analysis_types}")
            
            # Create tasks based on selected analysis types
            tasks = []
            
            # Summary and classification are always included
            tasks.append(self.classify_and_summarize_content())
            
            # Add other tasks based on selection
            if "Action Plan" in analysis_types:
                tasks.append(self.analyze_and_plan_content())
                
            if "Blog Post" in analysis_types:
                tasks.append(self.write_blog_post())
                
            if "LinkedIn Post" in analysis_types:
                tasks.append(self.write_linkedin_post())
                
            if "X Tweet" in analysis_types:
                tasks.append(self.write_tweet())
            
            logger.info(f"Created {len(tasks)} tasks for the crew")
            
            # Create the crew with explicit configuration
            logger.info("Creating Crew instance with the successfully created tasks")
            crew = Crew(
                agents=self.agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
            )
            
            logger.info(f"Successfully created crew with {len(crew.tasks)} tasks")
            return crew
            
        except Exception as e:
            logger.error(f"Error creating crew: {str(e)}", exc_info=True)
            raise 
