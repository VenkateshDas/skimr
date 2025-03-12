import sys
import traceback
from typing import Optional, Dict, Any, Union

from .crew import YouTubeAnalysisCrew
from .utils.logging import get_logger

logger = get_logger("main")

def display_results(crew_instance: YouTubeAnalysisCrew, result: str) -> None:
    """
    Display the results of the YouTube analysis.
    
    Args:
        crew_instance: The YouTubeAnalysisCrew instance.
        result: The result string from the crew execution.
    """
    print("\n\n########################")
    print("## YouTube Analysis Results")
    print("########################\n")
    
    # Display transcription results
    print("## TRANSCRIPTION")
    print("---------------")
    transcription_task = crew_instance.fetch_transcription()
    if transcription_task.output:
        print(f"Task Summary: {transcription_task.output.summary}")
        print("Transcription successfully fetched.")
    else:
        print("No transcription data available.")
    print()
    
    # Display content summary
    print("## CONTENT SUMMARY")
    print("------------------")
    summary_task = crew_instance.summarize_content()
    if summary_task.output:
        print(f"Task Summary: {summary_task.output.summary}")
        print(f"{summary_task.output.raw}")
    else:
        print("No summary available.")
    print()
    
    # Display content analysis
    print("## CONTENT ANALYSIS")
    print("------------------")
    analysis_task = crew_instance.analyze_content()
    if analysis_task.output:
        print(f"Task Summary: {analysis_task.output.summary}")
        print(f"{analysis_task.output.raw}")
    else:
        print("No analysis available.")
    print()
    
    # Display action plan
    print("## ACTION PLAN")
    print("-------------")
    action_plan_task = crew_instance.create_action_plan()
    if action_plan_task.output:
        print(f"Task Summary: {action_plan_task.output.summary}")
        print(f"{action_plan_task.output.raw}")
    else:
        print("No action plan available.")
    print()
    
    # Display final crew output
    print("## COMPLETE ANALYSIS")
    print("-------------------")
    print(result)

def run() -> Optional[str]:
    """
    Run the YouTube Analysis Crew with a user-provided YouTube URL.
    
    Returns:
        The analysis result as a string, or None if an error occurred.
    """
    logger.info("Starting YouTube Analysis Crew")
    print("## Welcome to YouTube Analysis Crew")
    print('-------------------------------')
    
    try:
        # Get YouTube URL from user
        youtube_url = input("Enter the YouTube URL to analyze: ")
        logger.info(f"User provided URL: {youtube_url}")
        
        # Create and run the crew
        logger.info("Creating YouTubeAnalysisCrew instance")
        crew_instance = YouTubeAnalysisCrew()
        
        # Create a crew with the URL
        logger.info("Creating crew with the URL")
        crew = crew_instance.crew()
        
        # Start the crew execution
        logger.info("Starting crew execution")
        # Only pass the youtube_url in the inputs
        inputs = {"youtube_url": youtube_url}
        crew_output = crew.kickoff(inputs=inputs)
        logger.info("Crew execution completed successfully")
        
        # Get the final result for return value
        result = str(crew_output)
        
        # Display the results
        display_results(crew_instance, result)
        
        logger.info("Analysis completed")
        
        return result
    
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        print("\nProcess interrupted by user. Exiting...")
        return None
    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        print(f"\nInvalid input: {str(e)}")
        return None
    except ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        print(f"\nConnection error: {str(e)}")
        print("Please check your internet connection and try again.")
        return None
    except Exception as e:
        logger.error(f"Error in run function: {str(e)}", exc_info=True)
        print(f"\nAn error occurred: {str(e)}")
        print("\nCheck the logs for more details.")
        return None

def train(n_iterations: int) -> None:
    """
    Train the crew for a given number of iterations.
    
    Args:
        n_iterations: The number of iterations to train for.
    
    Raises:
        ValueError: If n_iterations is not a positive integer.
        Exception: If an error occurs during training.
    """
    if n_iterations <= 0:
        raise ValueError("Number of iterations must be a positive integer")
    
    logger.info(f"Starting training with {n_iterations} iterations")
    try:
        # Example YouTube URL for training
        youtube_url = "https://youtu.be/WuzxmeUP6ro"
        logger.info(f"Using example URL for training: {youtube_url}")
        
        # Create the crew
        logger.info("Creating YouTubeAnalysisCrew instance for training")
        crew_instance = YouTubeAnalysisCrew()
        
        # Create a crew
        logger.info("Creating crew for training")
        crew = crew_instance.crew()
        
        # Train the crew for the specified number of iterations
        logger.info(f"Starting training for {n_iterations} iterations")
        inputs = {"youtube_url": youtube_url}
        
        # Display progress information
        print(f"\nTraining the crew for {n_iterations} iterations...")
        print("This may take some time. Please be patient.")
        
        # Start training
        crew.train(n_iterations=n_iterations, inputs=inputs)
        
        logger.info("Training completed successfully")
        print("\nTraining completed successfully!")
        
    except Exception as e:
        error_msg = f"An error occurred while training the crew: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {str(e)}", exc_info=True)
        print(f"Critical error: {str(e)}")
        print("Check the logs for more details.") 