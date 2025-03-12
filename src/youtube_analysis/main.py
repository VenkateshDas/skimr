import sys
import traceback
from typing import Optional, Dict, Any, Union

from .crew import YouTubeAnalysisCrew
from .utils.logging import get_logger
from .utils.youtube_utils import get_transcript

logger = get_logger("main")

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

        # Get the transcript from the YouTube URL
        transcript = get_transcript(youtube_url)
        logger.info(f"Successfully fetched transcript with {len(transcript)} characters")
        
        # Create and run the crew
        logger.info("Creating YouTubeAnalysisCrew instance")
        crew_instance = YouTubeAnalysisCrew()
        
        # Create a crew with the URL
        logger.info("Creating crew with the URL")
        crew = crew_instance.crew()
        
        # Start the crew execution
        logger.info("Starting crew execution")
        # Pass both the youtube_url and transcript in the inputs
        inputs = {"youtube_url": youtube_url, "transcript": transcript}
        crew_output = crew.kickoff(inputs=inputs)
        logger.info("Crew execution completed successfully")

        # Display the crew output
        print("\nCrew Output:")
        print(crew_output)
        
        # Get the token usage of the crew output
        token_usage = crew_output.token_usage
        logger.info(f"Token usage: {token_usage}")

        # Get the final result for return value
        result = str(crew_output)
        
        logger.info("Analysis completed")

        # Print the token usage
        print(f"\nToken usage: {token_usage}")
        
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