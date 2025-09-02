#!/usr/bin/env python3
"""
Example usage script for the AI Minutes Agent

This script demonstrates how to use the AI Minutes Agent programmatically.
"""

from ai_minutes_agent import AIMinutesAgent

def main():
    """
    Example of using the AI Minutes Agent in your own code.
    """
    # Initialize the agent
    agent = AIMinutesAgent(debug_mode=True)
    
    # Process a folder of PDF files
    folder_path = "minutes"
    
    print("Starting AI Minutes Agent Example...")
    
    try:
        # Process the folder and get results
        results = agent.process_folder(folder_path)
        
        # Print summary
        agent.print_summary(results)
        
        # Export to CSV
        agent.export_to_csv(results, "example_output.csv")
        
        # Access the results programmatically
        print("\nProgrammatic access to results:")
        for year, year_data in sorted(results.items()):
            print(f"  📅 {year}:")
            for date, count in sorted(year_data.items()):
                print(f"    {date}: {count} public comments")
        
        # Get processing statistics
        stats = agent.processing_stats
        print(f"\nProcessing Statistics:")
        print(f"  Total files processed: {stats['processed_files']}")
        print(f"  Total comments found: {stats['total_comments']}")
        print(f"  Success rate: {stats['processed_files']/stats['total_files']*100:.1f}%")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
