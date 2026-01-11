from django.core.management.base import BaseCommand

import asyncio

from parser.stepik_parser import StepikParser


class Command(BaseCommand):
    help = "Запуск парсера курсов Stepik"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Запуск парсера..."))
        try:
            asyncio.run(self.start_parsing())
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\nПарсинг остановлен пользователем\n")
            )

    async def start_parsing(self):
        parser = StepikParser(10)

        try:
            courses_data, course_ids = await parser.parse()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Успешно спарсил {len(course_ids)} курсов со Stepik"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))
        finally:
            await parser.session.close()
