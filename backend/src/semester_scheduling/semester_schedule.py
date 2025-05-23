from itertools import product
from itertools import combinations
from bs4 import BeautifulSoup
import requests
import re
import json
from datetime import datetime
from data_templates.semester_course import SemesterCourse


class SemesterScheduler:
    def __init__(self, semester_class_codes):
        self.semester_class_codes = semester_class_codes  # give it a list of
        # course codes that the user wants to take for the semester
        self.semester_class_data = {}
        self.semester_courses_grouped_by_code = []
        self.valid_semester_schedules = []
        self.have_valid_semester_schedules = False
        
    def get_semester_class_data(self):
        """Fetch course data from UF API for all course codes and populate self.semester_class_data."""

        for course_code in self.semester_class_codes:
            url = f"https://one.uf.edu/apix/soc/schedule?ai=false&auf=false&category=CWSP&class-num=&course-code={course_code}&course-title=&cred-srch=&credits=&day-f=&day-m=&day-r=&day-s=&day-t=&day-w=&dept=&eep=&fitsSchedule=false&ge=&ge-b=&ge-c=&ge-d=&ge-h=&ge-m=&ge-n=&ge-p=&ge-s=&instructor=&last-control-number=0&level-max=&level-min=&no-open-seats=false&online-a=&online-c=&online-h=&online-p=&period-b=&period-e=&prog-level=&qst-1=&qst-2=&qst-3=&quest=false&term=2258&wr-2000=&wr-4000=&wr-6000=&writing=false&var-cred=&hons=false"

            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"Error fetching data for {course_code}: {e}")
                continue

            if course_code not in self.semester_class_data:
                self.semester_class_data[course_code] = []

            for course_data in data:
                for course in course_data.get('COURSES', []):
                    code = course.get('code', '')
                    if code != course_code:
                        continue
                    name = course.get('name', '')
                    department = course.get('sections', [{}])[0].get('deptName', '')
                    gen_ed = course.get('sections', [{}])[0].get('genEd', [])

                    for section in course.get('sections', []):
                        credit = section.get('credits', 0)
                        unique_id = section.get('classNumber', '')
                        instructors = [instr.get('name', '') for instr in section.get('instructors', [])]
                        meet_times = section.get('meetTimes', [])
                        final_exam_date = section.get('finalExam', '')
                        class_dates = f"{section.get('startDate', '')} - {section.get('endDate', '')}"
                        additional_course_fee = section.get('courseFee', 0)
                        mode_type = section.get('sectWeb', '')  # e.g., 'PC' for in-person

                        # Format times and locations
                        period_lookup = {
                            "0725": "Period 1", "0830": "Period 2", "0935": "Period 3",
                            "1040": "Period 4", "1145": "Period 5", "1250": "Period 6",
                            "1355": "Period 7", "1500": "Period 8", "1605": "Period 9",
                            "1710": "Period 10", "1815": "Period 11", "1920": "Period 12"
                        }

                        def convert_to_military(time_str):
                            dt = datetime.strptime(time_str.strip(), '%I:%M %p')
                            return dt.strftime('%H%M')

                        # Initialize reformatted times list
                        formatted_times = []
                        location_groups = {}

                        for mt in meet_times:
                            day = mt.get('meetDays', '')  # E.g., "MWF"
                            raw_start = mt.get('meetTimeBegin', '')
                            raw_end = mt.get('meetTimeEnd', '')
                            location = f"{mt.get('meetBuilding', '')} {mt.get('meetRoom', '')}".strip()

                            if not raw_start or not raw_end:
                                continue

                            try:
                                start_time = convert_to_military(raw_start)
                                end_time = convert_to_military(raw_end)
                            except ValueError:
                                continue

                            period = period_lookup[start_time]
                            day_dict = {d: [start_time, end_time, period] for d in day}

                            # Group by location
                            if location not in location_groups:
                                location_groups[location] = {}
                            location_groups[location].update(day_dict)

                        # Convert location groups to formatted times
                        for location, times in location_groups.items():
                            formatted_times.append(times)

                        times = formatted_times if formatted_times else []

                        locations = list(location_groups.keys()) if (
                            location_groups) else ["Online"]

                        # Fetch instructor ratings
                        instructor_ratings = []
                        level_of_difficulty = "N/A"
                        would_take_again = "N/A"
                        if instructors:
                            prof_rating = self.professor_rating(instructors[0])
                            instructor_ratings = [prof_rating.get('overall_rating', 'N/A')]
                            level_of_difficulty = prof_rating.get('level_of_difficulty', 'N/A')
                            would_take_again = prof_rating.get('would_take_again', 'N/A')

                        # Derive subject from course code (e.g., 'COP' from 'COP4600')
                        subject = ''.join([c for c in code if c.isalpha()])

                        if not final_exam_date:
                            final_exam_date = "N/A"

                        # Append SemesterCourse object
                        self.semester_class_data[code].append(
                            SemesterCourse(
                                code=code,
                                credit=credit,
                                name=name,
                                subject=subject,
                                unique_id=unique_id,
                                times=times,
                                locations=locations,
                                instructors=instructors,
                                instructor_ratings=instructor_ratings,
                                mode_type=mode_type,
                                final_exam_date=final_exam_date,
                                class_dates=class_dates,
                                department=department,
                                gen_ed=gen_ed,
                                level_of_difficulty=level_of_difficulty,
                                would_take_again=would_take_again
                            )
                        )
        # self.semester_class_data = func() # call webscrapper function that
        # self.semester_class_data = func() # call the API Hieu used that
        # (using the semester_course class as a data holder/template)
        # returns the data in dictionary form with the keys being the course
        # code and the values being a list of the semester_course objects
        # associated with said course code

    def professor_rating(self, professor_name):
        # Construct the search URL
        search_url = f"https://www.ratemyprofessors.com/search/professors/1100?q={professor_name.replace(' ', '%20')}"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        # Send a GET request to the search page
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            return {"error": "Failed to retrieve search results."}

        # Parse the search results page
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find the first professor link
        professor_link = soup.find('a', href=re.compile(r'/professor/\d+'))
        if not professor_link:
            return {"error": "Professor not found."}

        # Construct the professor's page URL
        professor_url = f"https://www.ratemyprofessors.com{professor_link['href']}"
        # Send a GET request to the professor's page
        prof_response = requests.get(professor_url, headers=headers)
        if prof_response.status_code != 200:
            return {"error": "Failed to retrieve professor page."}

        # Parse the professor's page
        prof_soup = BeautifulSoup(prof_response.text, 'html.parser')

        # Extract overall rating
        overall_rating_tag = prof_soup.find('div', class_='RatingValue__Numerator-qw8sqy-2')
        overall_rating = overall_rating_tag.text.strip() if overall_rating_tag else "N/A"

        # Extract level of difficulty
        difficulty_tag = prof_soup.find('div', class_='FeedbackItem__FeedbackNumber-uof32n-1')
        difficulty = difficulty_tag.text.strip() if difficulty_tag else "N/A"

        # Extract "would take again" percentage
        would_take_again_tag = prof_soup.find_all('div', class_='FeedbackItem__FeedbackNumber-uof32n-1')
        would_take_again = would_take_again_tag[1].text.strip() if len(would_take_again_tag) > 1 else "N/A"

        return {
            "professor": professor_name,
            "overall_rating": overall_rating,
            "level_of_difficulty": difficulty,
            "would_take_again": would_take_again
        }

    def get_all_valid_semester_schedules(
        self, earliest_time="", latest_time="", period_blackouts=None,
        day_blackouts=None, min_instructor_rating="0",
        max_level_of_difficulty="", min_would_take_again=""
    ):
        self.valid_semester_schedules = []

        self.semester_courses_grouped_by_code = list(
            self.semester_class_data.values())

        all_class_combos = list(product(*self.semester_courses_grouped_by_code))

        for class_combo in all_class_combos:
            valid_class_combo = True
            all_class_pairs = list(combinations(class_combo, 2))

            for class_pair in all_class_pairs:
                if not class_pair[0].is_compatible(class_pair[1]):
                    valid_class_combo = False
                    break

            for sem_class in class_combo:
                if not sem_class.meets_requirements(
                        earliest_time=earliest_time, latest_time=latest_time,
                        period_blackouts=period_blackouts,
                        day_blackouts=day_blackouts,
                        min_instructor_rating=min_instructor_rating,
                        max_level_of_difficulty=max_level_of_difficulty,
                        min_would_take_again=min_would_take_again):
                    valid_class_combo = False
                    break

            if valid_class_combo:
                self.valid_semester_schedules.append(list(class_combo))

        if len(self.valid_semester_schedules) != 0:
            self.have_valid_semester_schedules = True

    def print_valid_semester_schedules(self, extra_verbose=False):
        if self.have_valid_semester_schedules:
            for i, valid_semester_schedule in (
                    enumerate(self.valid_semester_schedules)):
                print(f"***************** Valid Schedule #{i+1} "
                      f"*****************")
                for j, course in enumerate(valid_semester_schedule):
                    print(f" --------------- Course #{j+1} ---------------")
                    if extra_verbose:
                        print(course)
                    else:
                        print(f"{course.code} {course.name} "
                              f"(#{course.unique_id})")
                print("*****************************************************")
        else:
            print("No valid semester schedule found.")


# Call this function when trying to get the data for the frontend
def get_valid_semester_schedules(
    codes, filters, verbose=False, extra_verbose=False
):
    scheduler = SemesterScheduler(codes)
    scheduler.get_semester_class_data()
    max_number_of_class_combos = 1

    for courses in scheduler.semester_class_data.values():
        max_number_of_class_combos *= len(courses)

    if verbose:
        for code, courses in scheduler.semester_class_data.items():
            print(f"Course {code} sections:")
            for course in courses:
                if extra_verbose:
                    print(course)
                else:
                    print(f"{course.code} {course.name} (#{course.unique_id})")
                print("-" * 50)

    if verbose:
        print("\nAll valid combos of classes with the given filters")
    scheduler.get_all_valid_semester_schedules(
        earliest_time=filters["earliest_time"],
        latest_time=filters["latest_time"],
        period_blackouts=filters["period_blackouts"],
        day_blackouts=filters["day_blackouts"],
        min_instructor_rating=filters["min_instructor_rating"],
        max_level_of_difficulty=filters["max_level_of_difficulty"],
        min_would_take_again=filters["min_would_take_again"]
    )
    if verbose:
        scheduler.print_valid_semester_schedules(extra_verbose=extra_verbose)

    num_valid_combos = len(scheduler.valid_semester_schedules)
    percent_valid_over_total = (num_valid_combos/max_number_of_class_combos)*100
    print(
        f"{num_valid_combos}/{max_number_of_class_combos} "
        f"({percent_valid_over_total:.2f}%) valid semester schedules found "
        f"out of all possible class combos."
        )

    return scheduler.valid_semester_schedules


def main():
    codes = ["MAC2313", "PHY2049", "PHY2049L", "CAP4641", "COP4600"]
    # These are the default filters (that is, they technically don't filter and
    # this combination gives the max number of valid schedules for any set of
    # class codes).
    filters = {
        "earliest_time": "",
        "latest_time": "",
        "period_blackouts": [],
        "day_blackouts": [],
        "min_instructor_rating": "",
        "max_level_of_difficulty": "",
        "min_would_take_again": ""
    }

    valid_schedules = get_valid_semester_schedules(
        codes, filters, verbose=False, extra_verbose=False
    )


if __name__ == "__main__":
    main()
