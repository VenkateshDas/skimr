from typing import List
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from .tools import YouTubeTranscriptionTool
from .utils.logging import get_logger

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI

logger = get_logger("crew")

@CrewBase
class YouTubeAnalysisCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self, model_name="gpt-4o-mini", temperature=0.2):
        logger.info(f"Initializing YouTubeAnalysisCrew with model: {model_name}, temperature: {temperature}")
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
    
    @agent
    def fetcher_agent(self) -> Agent:
        logger.debug("Creating fetcher agent")
        return Agent(
            config=self.agents_config['fetcher_agent'],
            verbose=True,
            llm=self.llm,
            tools=[YouTubeTranscriptionTool()]
        )
    
    @task
    def fetch_transcription(self) -> Task:
        """
        Creates a task to fetch the transcription of a YouTube video.
        
        Returns:
            Task: A CrewAI task for fetching the transcription.
        """
        logger.info("Creating fetch transcription task")
        return Task(
            config=self.tasks_config['fetch_transcription'],
            agent=self.fetcher_agent()
        )
    
    @agent
    def summarizer_agent(self) -> Agent:
        logger.debug("Creating summarizer agent")
        return Agent(
            config=self.agents_config['summarizer_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def summarize_content(self) -> Task:
        """
        Creates a task to summarize the video content based on its transcription.
        
        Returns:
            Task: A CrewAI task for summarizing the content.
        """
        logger.info("Creating summarize content task")
        return Task(
            config=self.tasks_config['summarize_content'],
            agent=self.summarizer_agent(),
            context=[self.fetch_transcription()]
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
    def analyze_content(self) -> Task:
        """
        Creates a task to analyze the video content based on its transcription and summary.
        
        Returns:
            Task: A CrewAI task for analyzing the content.
        """
        logger.info("Creating analyze content task")
        return Task(
            config=self.tasks_config['analyze_content'],
            agent=self.analyzer_agent(),
            context=[self.fetch_transcription(), self.summarize_content()]
        )
    
    @agent
    def advisor_agent(self) -> Agent:
        logger.debug("Creating advisor agent")
        return Agent(
            config=self.agents_config['advisor_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def create_action_plan(self) -> Task:
        """
        Creates a task to create an action plan based on the video content analysis.
        
        Returns:
            Task: A CrewAI task for creating an action plan.
        """
        logger.info("Creating action plan task")
        return Task(
            config=self.tasks_config['create_action_plan'],
            agent=self.advisor_agent(),
            context=[self.fetch_transcription(), self.summarize_content(), self.analyze_content()]
        )
    
    @crew
    def crew(self) -> Crew:
        """
        Creates the YouTube Analysis Crew.
        
        Returns:
            Crew: A CrewAI Crew instance configured for YouTube analysis.
        """
        logger.info("Creating YouTube Analysis Crew")
        try:         
            logger.info("Creating crew with all agents and tasks")
            return Crew(
                agents=self.agents,
                tasks=self.tasks,
                process=Process.sequential,
                verbose=True,
            )
        except Exception as e:
            logger.error(f"Error creating crew: {str(e)}", exc_info=True)
            raise 