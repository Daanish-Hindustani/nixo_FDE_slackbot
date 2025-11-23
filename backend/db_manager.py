#!/usr/bin/env python3
"""
Database initialization and management script for FDE Slackbot.

This script provides utilities for:
- Initializing a fresh database
- Resetting the database
- Viewing database statistics
- Inspecting database contents
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from database import create_db_and_tables, engine
from sqlmodel import Session, select, func
from models import Issue, Message


def init_database():
    """Initialize a fresh database with all tables."""
    print("Initializing database...")
    create_db_and_tables()
    print("✓ Database initialized successfully!")
    print(f"  Location: {Path('database.db').absolute()}")


def reset_database():
    """Reset the database by removing and recreating it."""
    db_path = Path("database.db")
    
    if db_path.exists():
        confirm = input("⚠️  This will delete all data. Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return
        
        db_path.unlink()
        print("✓ Deleted existing database")
    
    create_db_and_tables()
    print("✓ Created fresh database")


def show_stats():
    """Display database statistics."""
    with Session(engine) as session:
        # Count issues by status
        total_issues = session.exec(select(func.count(Issue.id))).one()
        open_issues = session.exec(
            select(func.count(Issue.id)).where(Issue.status == "open")
        ).one()
        resolved_issues = session.exec(
            select(func.count(Issue.id)).where(Issue.status == "resolved")
        ).one()
        
        # Count messages
        total_messages = session.exec(select(func.count(Message.id))).one()
        relevant_messages = session.exec(
            select(func.count(Message.id)).where(Message.is_relevant == True)
        ).one()
        
        # Count by classification
        classifications = session.exec(
            select(Message.classification, func.count(Message.id))
            .group_by(Message.classification)
        ).all()
        
        print("\n" + "="*60)
        print("DATABASE STATISTICS")
        print("="*60)
        print(f"\nIssues:")
        print(f"  Total:    {total_issues}")
        print(f"  Open:     {open_issues}")
        print(f"  Resolved: {resolved_issues}")
        
        print(f"\nMessages:")
        print(f"  Total:    {total_messages}")
        print(f"  Relevant: {relevant_messages}")
        
        if classifications:
            print(f"\nClassifications:")
            for classification, count in classifications:
                print(f"  {classification}: {count}")
        
        print("="*60 + "\n")


def list_issues():
    """List all issues in the database."""
    with Session(engine) as session:
        issues = session.exec(select(Issue)).all()
        
        if not issues:
            print("No issues found in database.")
            return
        
        print("\n" + "="*60)
        print("ISSUES")
        print("="*60 + "\n")
        
        for issue in issues:
            print(f"ID: {issue.id}")
            print(f"Title: {issue.title}")
            print(f"Status: {issue.status}")
            print(f"Classification: {issue.classification}")
            print(f"Created: {issue.created_at}")
            
            # Count messages
            msg_count = session.exec(
                select(func.count(Message.id)).where(Message.issue_id == issue.id)
            ).one()
            print(f"Messages: {msg_count}")
            print("-" * 60)


def list_messages(issue_id=None):
    """List messages, optionally filtered by issue_id."""
    with Session(engine) as session:
        if issue_id:
            messages = session.exec(
                select(Message).where(Message.issue_id == issue_id)
            ).all()
            title = f"MESSAGES FOR ISSUE {issue_id}"
        else:
            messages = session.exec(select(Message)).all()
            title = "ALL MESSAGES"
        
        if not messages:
            print("No messages found.")
            return
        
        print("\n" + "="*60)
        print(title)
        print("="*60 + "\n")
        
        for msg in messages:
            print(f"ID: {msg.id}")
            print(f"User: {msg.user_id}")
            print(f"Channel: {msg.channel_id}")
            print(f"Text: {msg.text[:100]}{'...' if len(msg.text) > 100 else ''}")
            print(f"Classification: {msg.classification} (confidence: {msg.confidence:.2f})")
            print(f"Relevant: {msg.is_relevant}")
            print(f"Issue ID: {msg.issue_id}")
            print("-" * 60)


def main():
    """Main entry point with menu."""
    print("\n" + "="*60)
    print("FDE SLACKBOT - DATABASE MANAGEMENT")
    print("="*60)
    print("\nOptions:")
    print("  1. Initialize database (first time setup)")
    print("  2. Reset database (delete all data)")
    print("  3. Show statistics")
    print("  4. List all issues")
    print("  5. List all messages")
    print("  6. List messages for specific issue")
    print("  7. Exit")
    
    choice = input("\nSelect an option (1-7): ").strip()
    
    if choice == "1":
        init_database()
    elif choice == "2":
        reset_database()
    elif choice == "3":
        show_stats()
    elif choice == "4":
        list_issues()
    elif choice == "5":
        list_messages()
    elif choice == "6":
        issue_id = input("Enter issue ID: ").strip()
        try:
            list_messages(int(issue_id))
        except ValueError:
            print("Invalid issue ID!")
    elif choice == "7":
        print("Goodbye!")
        sys.exit(0)
    else:
        print("Invalid option!")


if __name__ == "__main__":
    main()
