import requests
from fake_useragent import UserAgent
import json
import time
import os

CATEGORIES_NUMS_URL = "https://cdn.stepik.net/media/files/rubricator_prod_20251224.json"
COURSE_LISTS_API = "https://stepik.org/api/course-lists"
COURSES_API = "https://stepik.org/api/courses"
REVIEWS_API = "https://stepik.org/api/course-reviews"
USERS_API = "https://stepik.org/api/users"

def generate_headers():
    ua = UserAgent()
    return {
        "User-Agent": ua.random,
    }

def get_all_categories(url):
    categories_all = requests.get(url).json()
    categories_it = None
    
    for i in range(len(categories_all["subjects"])):
        if categories_all["subjects"][i]["title"] == "Информационные технологии":
            categories_it_nums = categories_all["subjects"][i]["meta_categories"]
            categories_it = [cat for cat in categories_all["meta_categories"] 
                           if cat["id"] in categories_it_nums]
            break
    
    if not categories_it:
        print("IT категории не найдены")
        return []

    all_course_lists = []
    for category in categories_it:
        all_course_lists.extend(category.get("course_lists", []))

    all_course_lists = list(set(all_course_lists))
    print(f"Найдено {len(categories_it)} IT категорий")

    return all_course_lists, categories_it

def get_courses_by_course_lists(course_list_ids):
    headers = generate_headers()
    
    params = [f"ids[]={cid}" for cid in course_list_ids]
    url = f"{COURSE_LISTS_API}?{'&'.join(params)}"
    
    print(f"Запрашиваем данные по {len(course_list_ids)} course_lists...")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        course_lists = data.get("course-lists", [])

        all_courses = {}
        for cl in course_lists:
            course_list_title = cl.get("title", "Unknown")
            course_ids = cl.get("courses", [])
            all_courses[course_list_title] = {
                "id": cl.get("id"),
                "title": course_list_title,
                "description": cl.get("description", ""),
                "course_count": len(course_ids),
                "course_ids": course_ids
            }
        
        return all_courses
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе: {e}")
        return {}

def get_course_reviews(course_id):
    headers = generate_headers()
    url = f"{REVIEWS_API}?course={course_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("course-reviews", [])
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе отзывов для курса {course_id}: {e}")
        return []

def get_user_info(user_ids):
    if not user_ids:
        return {}
    
    headers = generate_headers()
    params = [f"ids[]={uid}" for uid in user_ids]
    url = f"{USERS_API}?{'&'.join(params)}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        users = data.get("users", [])
        return {user["id"]: user for user in users}
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе информации о пользователях: {e}")
        return {}

def get_course_details(course_ids, batch_size=100):
    headers = generate_headers()
    all_course_details = []

    for i in range(0, len(course_ids), batch_size):
        batch = course_ids[i:i+batch_size]
        params = [f"ids[]={cid}" for cid in batch]
        url = f"{COURSES_API}?{'&'.join(params)}"
        
        print(f"Запрашиваем детали курсов {i+1}-{min(i+batch_size, len(course_ids))} из {len(course_ids)}...")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            courses = data.get("courses", [])
            all_course_details.extend(courses)
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе батча {i//batch_size + 1}: {e}")
        
        time.sleep(0.5)

    return all_course_details

def filter_course_data(course):
    reviews_summary = course.get("review_summary")
    avg_rating = None
    reviews_count = None
    if reviews_summary:
        avg_rating = reviews_summary.get("average")
        reviews_count = reviews_summary.get("count")

    return {
        "id": course.get("id"),
        "title": course.get("title"),
        "slug": course.get("slug"),
        "summary": course.get("summary"),
        "description": course.get("description"),
        "cover": course.get("cover"),
        "workload": course.get("workload"),
        "language": course.get("language"),
        "is_paid": course.get("is_paid"),
        "price": course.get("price"),
        "display_price": course.get("display_price"),
        "difficulty": course.get("difficulty"),
        "learners_count": course.get("learners_count"),
        "certificates_count": course.get("certificates_count"),
        "lessons_count": course.get("lessons_count"),
        "time_to_complete": course.get("time_to_complete"),
        "acquired_skills": course.get("acquired_skills"),
        "target_audience": course.get("target_audience"),
        "requirements": course.get("requirements"),
        "authors": course.get("authors"),
        "instructors": course.get("instructors"),
        "tags": course.get("tags"),
        "canonical_url": course.get("canonical_url"),
        "create_date": course.get("create_date"),
        "update_date": course.get("update_date"),
        "avg_rating": avg_rating,
        "reviews_count": reviews_count
    }

def save_courses_to_json(courses):
    output_dir = "courses_data"
    os.makedirs(output_dir, exist_ok=True)

    for idx, course in enumerate(courses):
        course_id = course.get("id")

        print(f"Обработка курса {idx+1}/{len(courses)}: {course.get('title')} (ID: {course_id})")

        reviews = get_course_reviews(course_id)

        user_ids = set()
        user_ids.update(course.get("authors", []))
        user_ids.update(course.get("instructors", []))
        for review in reviews:
            user_ids.add(review.get("user"))

        users_info = get_user_info(list(user_ids))

        course_data = {
            "course": course,
            "reviews": reviews,
            "users": users_info
        }

        filename = os.path.join(output_dir, f"course_{course_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(course_data, f, ensure_ascii=False, indent=2)
        time.sleep(0.3)

    print(f"\nВсе данные сохранены в директорию '{output_dir}'")

def main():
    course_list_ids, categories = get_all_categories(CATEGORIES_NUMS_URL)
    if not course_list_ids:
        print("Не удалось получить список course_lists")
        return

    for cat in categories:
        print(f"  - {cat['title']} (ID: {cat['id']}): {len(cat.get('course_lists', []))} course_lists")

    print("\n" + "="*50)
    courses_by_lists = get_courses_by_course_lists(course_list_ids)
    total_courses = 0
    for title, info in sorted(courses_by_lists.items(), key=lambda x: x[1]["course_count"], reverse=True):
        print(f"  {title}: {info['course_count']} курсов")
        total_courses += info["course_count"]

    all_unique_course_ids = set()
    for info in courses_by_lists.values():
        all_unique_course_ids.update(info["course_ids"])
    print(f"Уникальных курсов после дедупликации: {len(all_unique_course_ids)}")

    course_details = get_course_details(list(all_unique_course_ids))
    print(f"\nПолучено деталей о {len(course_details)} курсах")
    print(course_details[0])

    save_courses_to_json(course_details)

    return courses_by_lists, all_unique_course_ids

if __name__ == "__main__":
    courses_data, course_ids = main()