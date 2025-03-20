from typing import List
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

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
    def classifier_agent(self) -> Agent:
        logger.debug("Creating classifier agent")
        return Agent(
            config=self.agents_config['classifier_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def classify_video(self) -> Task:
        """
        Creates a task to classify the YouTube video based on its transcript.
        
        Returns:
            Task: A CrewAI task for classifying the video.
        """
        logger.info("Creating classify video task")
        return Task(
            config=self.tasks_config['classify_video'],
            agent=self.classifier_agent(),
            async_execution=True
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
            async_execution=True
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
            async_execution=True
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
            async_execution=True
        )
    
    @agent
    def report_writer_agent(self) -> Agent:
        logger.debug("Creating report writer agent")
        return Agent(
            config=self.agents_config['report_writer_agent'],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def write_report(self) -> Task:
        """
        Creates a task to write a comprehensive report based on all previous analyses.
        
        Returns:
            Task: A CrewAI task for writing a report.
        """
        logger.info("Creating write report task")
        return Task(
            config=self.tasks_config['write_report'],
            agent=self.report_writer_agent(),
            context=[self.classify_video(), self.summarize_content(), self.analyze_content(), self.create_action_plan()]
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
            logger.info(f"Available tasks: {[t.__name__ if hasattr(t, '__name__') else str(t) for t in self.tasks]}")
            
            # Create tasks with explicit debugging
            tasks = []
            task_methods = [
                self.classify_video, 
                self.summarize_content, 
                self.analyze_content, 
                self.create_action_plan, 
                self.write_report
            ]
            
            logger.info(f"Creating {len(task_methods)} tasks")
            
            # Enhanced error handling for task creation
            task_creation_errors = []
            for task_method in task_methods:
                try:
                    logger.info(f"Creating task from method: {task_method.__name__}")
                    task = task_method()
                    if task:
                        logger.info(f"Successfully created task: {task.name}")
                        tasks.append(task)
                    else:
                        error_msg = f"Task {task_method.__name__} returned None"
                        logger.error(error_msg)
                        task_creation_errors.append(error_msg)
                except Exception as task_error:
                    error_msg = f"Error creating task {task_method.__name__}: {str(task_error)}"
                    logger.error(error_msg, exc_info=True)
                    task_creation_errors.append(error_msg)
            
            logger.info(f"Created {len(tasks)} tasks for the crew")
            
            if len(tasks) == 0:
                error_msg = "No tasks were created successfully. Check task creation errors."
                logger.error(error_msg)
                if task_creation_errors:
                    logger.error(f"Task creation errors: {'; '.join(task_creation_errors)}")
                raise RuntimeError(error_msg)
            
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