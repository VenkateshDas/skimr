"""CrewAI workflow for YouTube video analysis."""

import os
from typing import List, Optional
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, crew, task

from ..utils.logging import get_logger
from ..core.llm_manager import LLMManager
from ..core.config import config

logger = get_logger("crew")

# Ensure we can find the config files
def get_config_path(filename: str) -> str:
    """Get the absolute path to a config file."""
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
    return os.path.join(config_dir, filename)


@CrewBase
class YouTubeAnalysisCrew:
    # Use absolute paths to the config files
    agents_config = get_config_path('agents.yaml')
    tasks_config = get_config_path('tasks.yaml')
    
    def __init__(self, model_name: str = None, temperature: float = None):
        # Use config defaults if not provided
        if model_name is None:
            model_name = config.llm.default_model
        if temperature is None:
            temperature = config.llm.default_temperature
            
        logger.info(f"Initializing YouTubeAnalysisCrew with model: {model_name}, temperature: {temperature}")
        self.llm_manager = LLMManager()
        # Get CrewAI LLM instance
        from ..core.llm_manager import LLMConfig
        llm_config = LLMConfig(model=model_name, temperature=temperature)
        self.llm = self.llm_manager.get_crewai_llm(llm_config)

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
        Creates a task to analyze the video content and create actionable plans.
        
        Returns:
            Task: A CrewAI task for analyzing and planning content.
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
            llm=self.llm
        )
    
    @agent
    def linkedin_post_writer_agent(self) -> Agent:
        logger.debug("Creating LinkedIn post writer agent")
        return Agent(
            config=self.agents_config['linkedin_post_writer_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @agent
    def tweet_writer_agent(self) -> Agent:
        logger.debug("Creating tweet writer agent")
        return Agent(
            config=self.agents_config['tweet_writer_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def write_blog_post(self) -> Task:
        """
        Creates a task to write a blog post based on the video analysis.
        
        Returns:
            Task: A CrewAI task for writing a blog post.
        """
        logger.info("Creating write blog post task")
        return Task(
            config=self.tasks_config['write_blog_post'],
            agent=self.blog_writer_agent(),
            async_execution=False
        )
    
    @task
    def write_linkedin_post(self) -> Task:
        """
        Creates a task to write a LinkedIn post based on the video analysis.
        
        Returns:
            Task: A CrewAI task for writing a LinkedIn post.
        """
        logger.info("Creating write LinkedIn post task")
        return Task(
            config=self.tasks_config['write_linkedin_post'],
            agent=self.linkedin_post_writer_agent(),
            async_execution=False
        )
    
    @task
    def write_tweet(self) -> Task:
        """
        Creates a task to write a tweet based on the video analysis.
        
        Returns:
            Task: A CrewAI task for writing a tweet.
        """
        logger.info("Creating write tweet task")
        return Task(
            config=self.tasks_config['write_tweet'],
            agent=self.tweet_writer_agent(),
            async_execution=False
        )
    
    @crew
    def crew(self, analysis_types: tuple = None) -> Crew:
        """
        Assembles the YouTube Analysis crew with specified analysis types.
        
        Args:
            analysis_types: Tuple of analysis types to include
            
        Returns:
            Crew: A CrewAI crew configured for YouTube video analysis.
        """
        if analysis_types is None:
            analysis_types = tuple(config.analysis.available_analysis_types)
            
        logger.info(f"Creating crew with analysis types: {analysis_types}")
        
        # Always include the base classification task
        tasks = [self.classify_and_summarize_content()]
        
        # Add tasks based on analysis types
        if "Action Plan" in analysis_types:
            tasks.append(self.analyze_and_plan_content())
        
        if "Blog Post" in analysis_types:
            tasks.append(self.write_blog_post())
        
        if "LinkedIn Post" in analysis_types:
            tasks.append(self.write_linkedin_post())
        
        if "X Tweet" in analysis_types:
            tasks.append(self.write_tweet())
        
        # Extract unique agents from tasks
        agents = []
        seen_agents = set()
        for task in tasks:
            if hasattr(task, 'agent') and task.agent not in seen_agents:
                agents.append(task.agent)
                seen_agents.add(task.agent)
        
        logger.info(f"Crew created with {len(agents)} agents and {len(tasks)} tasks")
        
        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        ) 