from bs4 import BeautifulSoup
import requests 
import os
from pprint import pprint
import json 
from urllib.parse import urljoin

def fetch_html(url: str) -> BeautifulSoup:
    '''
    Reads the course's website as an html file and creates a BeautifulSoup object.
    '''

    html = requests.get(url, timeout=15)
    html.raise_for_status()
    course_news = BeautifulSoup(html.text, "html.parser")

    return course_news

def parse_announcements(course_news: BeautifulSoup) -> dict:
    '''
    Reads the table from the BeautifulSoup object and creates a nested dictionary 
    with the date as a key, and in the values, an "announcement" key that contains the 
    announcement as a string and a "links" key that contains the announcement's link(s) 
    in a list.
    '''

    rows = course_news.find_all("tr")
    updates = {}

    for row in range(1, len(rows)):
        date = rows[row].find_all("td")[0].get_text()
        news_item = rows[row].find_all("td")[1]
        announcement = news_item.get_text()
        links = [link.get("href") for link in news_item.find_all("a")]

        updates[date] = {}
        updates[date]["announcement"] = announcement
        updates[date]["links"] = links 

    return updates

def detect_changes(previous: dict, current: dict) -> dict:
    '''
    Returns a new announcement, if any, in a dictionary by comparing a dictionaries containing 
    previous and current announcement information 
    '''
    #This function is just going to check for new keys. If the website either edits 
    #announcements or does multiple announcements on the same date, then it would be beneficial
    #to compare each date's values for the announcement key or have the identifying key be 
    #something other than the date. But for initial implementation purposes, I'm just going to compare 
    #dates.
    new = {}
    for key in current.keys():
        if key not in previous.keys():
            new[key] = current[key] 

    return new  

def save_announcements(current: dict) -> None:
    '''
    Takes the existing updates dictionary and writes it to the announcements.json file
    '''
    with open("announcements.json", "w", encoding="utf-8") as file:
        json.dump(current, file, indent=4)

def load_announcements() -> dict|None:
    '''
    Loads the updates dictionary from the announcements.json file 
    '''
    try:
        with open("announcements.json", "r", encoding="utf-8") as file:
            previous = json.load(file)
        return previous
    except FileNotFoundError:
        return None

def parse_schedule(new: dict, item: str) -> dict: 
    '''
    Retrieves the schedule link, gets its html text, reads it, and places the assignment name and 
    due date into a dictionary.
    '''
    assignment_and_due_date = []
    base = "https://ics.uci.edu/~thornton/icsh32/"
    print(new)
    for key in new:
        for link in new[key]["links"]:
            if link.startswith("Schedule"):
                schedule_url = urljoin(base, link)

    schedule = fetch_html(schedule_url)
    container = schedule.find("table").find_all("tr", recursive=False)[1]
    schedule_rows = container.find_all("tr", recursive=False)

    for entry in schedule_rows:
        if entry.get("class") is None:
            cells = entry.find_all("td")
            first_cell = cells[0].get_text(" ", strip=True)
            fourth_cell = cells[3].get_text(" ", strip=True)
            if first_cell.startswith(("M", "W", "F")) and item in fourth_cell:
                due_date = expand_abbrev(first_cell)
                assignment = fourth_cell[:-12]
                assignment_and_due_date.append(assignment + " due " + due_date + " 11:59pm")

    return assignment_and_due_date

def expand_abbrev(due_date: str) -> str:
    '''
    Replaces a single-letter abbreviation of a day into the full version (ex. M->Monday)
    '''
    date, rest = due_date.split(" ")
    days = {"M": "Monday", "W": "Wednesday", "F": "Friday"}
    date = days[date] + " " + rest

    return date

def get_notif_content(new: dict) -> list[str]:
    '''
    Looks for for either projects or exercise set mentions in the 
    announcement and adds the most recent news item to a general notification content list.
    '''
    notif_content = []
    exercises = "Exercise"
    project = "Project"

    for key in new:
        if exercises in new[key]["announcement"]:
            sets = parse_schedule(new, exercises)
            notif_content.append(sets[-1])

    for key in new:
        if project in new[key]["announcement"]:
            projects = parse_schedule(new, project)
            notif_content.append(projects[-1])

    return notif_content

def send_notif(notif_content: list[str], code: str|int) -> None:
    '''
    Sends a notification with the updates through ntfy
    '''
    course = str(code).upper()
    topic = os.environ[f"NTFY_{course}_TOPIC"]
    #topic = f"thornton-{course}-notifs-m1102e16"
    url = f"https://ntfy.sh/{topic}"

    notifs = "\n".join(notif_content)

    response = requests.post(
        url, 
        data=notifs,
        headers={
            "Title": f"New {course} announcement",
            "Click": f"https://ics.uci.edu/~thornton/ics{course.lower()}/Schedule.html"
        },
        timeout=15
    )
    response.raise_for_status()

if __name__=="__main__":
    course_news = "https://ics.uci.edu/~thornton/icsh32/index.html"
    current = parse_announcements(fetch_html(course_news))
    previous = load_announcements()
    if previous is None:
        save_announcements(current)
    else:
        new = detect_changes(previous, current)
        if new!={}:
            notif_content = get_notif_content(new)
            send_notif(notif_content, "h32")
            save_announcements(current)




