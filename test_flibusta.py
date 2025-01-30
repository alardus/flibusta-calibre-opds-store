import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, quote
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchResult:
    """Простая замена SearchResult из Calibre"""
    DRM_UNLOCKED = "DRM Free"
    
    def __init__(self):
        self.title = ""
        self.author = ""
        self.detail_item = ""
        self.price = ""
        self.drm = self.DRM_UNLOCKED
        self.downloads = {}
        self.formats = ""

class FlibustaTest:
    def __init__(self):
        self.base_url = 'https://flub.flibusta.is'
        self.opds_search_url = 'https://raw.githubusercontent.com/alardus/flibusta-calibre-opds-store/main/opds-opensearch.xml'
        self.supported_formats = ['epub', 'fb2', 'mobi']
        self.timeout = 30

    def get_search_url_template(self):
        """Получение шаблона URL для поиска из конфигурации"""
        try:
            response = requests.get(self.opds_search_url, timeout=self.timeout)
            root = ET.fromstring(response.content)
            
            # Находим элемент Url с type="application/atom+xml"
            ns = {'opensearch': 'http://a9.com/-/spec/opensearch/1.1/'}
            url_element = root.find(".//opensearch:Url[@type='application/atom+xml']", ns)
            
            if url_element is not None:
                template = url_element.get('template')
                logger.info(f"Получен шаблон URL: {template}")
                return template
            else:
                logger.error("Не найден шаблон URL для поиска")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении шаблона URL: {str(e)}")
            return None

    def search_books(self, query, max_results=10):
        """Поиск книг"""
        try:
            template = self.get_search_url_template()
            if not template:
                return []
            
            search_url = template.replace('{searchTerms}', quote(query))
            if '{startPage?}' in search_url:
                search_url = search_url.replace('&pageNumber={startPage?}', '')
            
            logger.info(f"Выполняем поиск по URL: {search_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/atom+xml,application/xml,text/xml,*/*'
            }
            
            response = requests.get(search_url, timeout=self.timeout, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Ошибка при поиске: {response.status_code}")
                return []
            
            root = ET.fromstring(response.content)
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'dc': 'http://purl.org/dc/terms/',
            }
            
            entries = root.findall('.//atom:entry', namespaces)
            results = []
            
            for entry in entries[:max_results]:
                try:
                    result = SearchResult()
                    result.title = entry.find('.//atom:title', namespaces).text
                    author_elem = entry.find('.//atom:author/atom:name', namespaces)
                    result.author = author_elem.text if author_elem is not None else ''
                    result.detail_item = entry.find('.//atom:id', namespaces).text
                    
                    for link in entry.findall('.//atom:link', namespaces):
                        rel = link.get('rel')
                        href = link.get('href')
                        type = link.get('type')
                        
                        if rel and href and type:
                            if 'http://opds-spec.org/acquisition' in rel:
                                ext = self.custom_guess_extension(type)
                                if ext:
                                    result.downloads[ext] = urljoin(self.base_url, href)
                    
                    result.formats = ', '.join(result.downloads.keys())
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Ошибка при парсинге записи: {str(e)}")
                    continue
                    
            return results
                
        except Exception as e:
            logger.error(f"Ошибка при поиске книг: {str(e)}")
            return []

    def custom_guess_extension(self, type):
        """Определение расширения файла"""
        if 'application/fb2' in type:
            return 'FB2'
        elif 'application/epub' in type:
            return 'EPUB'
        elif 'application/x-mobipocket-ebook' in type:
            return 'MOBI'
        return None

    def test_connectivity(self):
        """Проверка доступности серверов"""
        try:
            logger.info("Проверка доступности основного сервера...")
            response = requests.get(self.base_url, timeout=self.timeout)
            logger.info(f"Статус основного сервера: {response.status_code}")
            
            logger.info("Проверка доступности конфигурации поиска...")
            response = requests.get(self.opds_search_url, timeout=self.timeout)
            logger.info(f"Статус конфигурации поиска: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке подключения: {str(e)}")
            return False

    def test_download_links(self, book):
        """Проверка ссылок на скачивание"""
        valid_links = []
        for format_type, url in book.downloads.items():
            try:
                logger.info(f"Проверка ссылки: {url}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*'
                }
                
                # Используем allow_redirects=True для следования редиректам
                response = requests.head(url, timeout=self.timeout, headers=headers, allow_redirects=True)
                logger.info(f"Финальный URL: {response.url}")
                logger.info(f"Статус ответа: {response.status_code}")
                logger.info(f"История редиректов: {len(response.history)}")
                logger.info(f"Заголовки ответа: {response.headers}")
                
                status = response.status_code == 200
                valid_links.append({
                    'url': response.url,  # Сохраняем финальный URL
                    'type': format_type,
                    'valid': status
                })
            except Exception as e:
                logger.error(f"Ошибка при проверке ссылки {url}: {str(e)}")
        return valid_links

    def debug_response(self, response):
        """Отладка ответа сервера"""
        logger.info(f"URL: {response.url}")
        logger.info(f"Статус: {response.status_code}")
        logger.info(f"Заголовки: {response.headers}")
        logger.info(f"Кодировка: {response.encoding}")
        logger.info(f"Контент: {response.text[:500]}...")  # Первые 500 символов ответа

    def test_search_types(self):
        """Тестирование разных типов поиска"""
        test_types = {
            'books': '/opds/search?searchTerm={query}&searchType=books',
            'authors': '/opds/search?searchTerm={query}&searchType=authors',
            'general': '/opds/search?searchTerm={query}',  # Поиск без указания типа
        }
        
        results = {}
        query = 'Пелевин'
        
        # Определяем пространства имен
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'dc': 'http://purl.org/dc/terms/',
        }
        
        for search_type, path_template in test_types.items():
            try:
                # Формируем полный URL
                search_url = urljoin(self.base_url, path_template.format(query=requests.utils.quote(query)))
                logger.info(f"\nТестирование поиска '{search_type}'")
                logger.info(f"URL: {search_url}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/atom+xml,application/xml,text/xml,*/*'
                }
                
                response = requests.get(search_url, timeout=self.timeout, headers=headers)
                logger.info(f"Статус ответа: {response.status_code}")
                
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    entries = root.findall('.//atom:entry', namespaces)
                    results[search_type] = {
                        'status': response.status_code,
                        'results_count': len(entries)
                    }
                    
                    # Показываем первые результаты
                    logger.info(f"Найдено результатов: {len(entries)}")
                    for i, entry in enumerate(entries[:2]):
                        title = entry.find('.//atom:title', namespaces).text
                        logger.info(f"  {i+1}. {title}")
                else:
                    results[search_type] = {
                        'status': response.status_code,
                        'results_count': 0
                    }
                    logger.error(f"Ошибка при поиске: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Ошибка при тестировании {search_type}: {str(e)}")
                results[search_type] = {
                    'status': 0,
                    'results_count': 0
                }
        
        return results

    def print_summary(self, results):
        """Вывод итогового отчета тестирования"""
        # Цветовые коды ANSI
        GREEN = '\033[92m'
        RED = '\033[91m'
        BLUE = '\033[94m'
        ENDC = '\033[0m'
        
        logger.info(f"\n{BLUE}=== ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ ==={ENDC}")
        
        # Блок 1: Подключение
        logger.info("\n1. Проверка подключения:")
        connectivity_ok = True
        if results.get('connectivity', {}).get('base_server') == 200:
            logger.info(f"{GREEN}✓ Основной сервер доступен{ENDC}")
        else:
            logger.info(f"{RED}✗ Проблемы с доступом к основному серверу{ENDC}")
            connectivity_ok = False
        
        if results.get('connectivity', {}).get('search_config') == 200:
            logger.info(f"{GREEN}✓ Конфигурация поиска доступна{ENDC}")
        else:
            logger.info(f"{RED}✗ Проблемы с доступом к конфигурации поиска{ENDC}")
            connectivity_ok = False
        
        if connectivity_ok:
            logger.info(f"{GREEN}Блок подключения: ОК{ENDC}")
        else:
            logger.info(f"{RED}Блок подключения: ОШИБКА{ENDC}")

        # Блок 2: Типы поиска
        logger.info("\n2. Проверка типов поиска:")
        search_ok = True
        search_types = results.get('search_types', {})
        for search_type, data in search_types.items():
            if data.get('status') == 200 and data.get('results_count', 0) > 0:
                logger.info(f"{GREEN}✓ {search_type}: найдено результатов - {data.get('results_count', 0)}{ENDC}")
            else:
                if data.get('status') != 200:
                    logger.info(f"{RED}✗ {search_type}: ошибка доступа (статус {data.get('status')}){ENDC}")
                else:
                    logger.info(f"{RED}✗ {search_type}: нет результатов{ENDC}")
                search_ok = False
        
        if search_ok:
            logger.info(f"{GREEN}Блок поиска: ОК{ENDC}")
        else:
            logger.info(f"{RED}Блок поиска: ОШИБКА{ENDC}")

        # Блок 3: Скачивание файлов
        logger.info("\n3. Проверка скачивания файлов:")
        downloads_ok = True
        downloads = results.get('downloads', {})
        for format_type, status in downloads.items():
            if status:
                logger.info(f"{GREEN}✓ {format_type}{ENDC}")
            else:
                logger.info(f"{RED}✗ {format_type}{ENDC}")
                downloads_ok = False
        
        if downloads_ok:
            logger.info(f"{GREEN}Блок скачивания: ОК{ENDC}")
        else:
            logger.info(f"{RED}Блок скачивания: ОШИБКА{ENDC}")

        # Общий вердикт
        logger.info(f"\n{BLUE}=== ОБЩИЙ ВЕРДИКТ ==={ENDC}")
        all_ok = all([
            connectivity_ok,
            search_ok,
            downloads_ok
        ])
        
        if all_ok:
            logger.info(f"{GREEN}✓ Все функции работают корректно{ENDC}")
        else:
            logger.info(f"{RED}✗ Есть проблемы в работе некоторых функций{ENDC}")

def main():
    tester = FlibustaTest()
    results = {
        'connectivity': {},
        'search_types': {},
        'downloads': {}
    }
    
    # Тест 1: Проверка подключения
    try:
        response = requests.get(tester.base_url, timeout=tester.timeout)
        results['connectivity']['base_server'] = response.status_code
    except:
        results['connectivity']['base_server'] = 0
        
    try:
        response = requests.get(tester.opds_search_url, timeout=tester.timeout)
        results['connectivity']['search_config'] = response.status_code
    except:
        results['connectivity']['search_config'] = 0

    if results['connectivity']['base_server'] != 200:
        logger.error("Тест подключения не пройден")
        tester.print_summary(results)
        return
    
    # Тест 2: Проверка разных типов поиска
    search_types_results = tester.test_search_types()
    results['search_types'] = search_types_results
    
    # Тест 3: Проверка скачивания
    test_query = "Пелевин"
    books = tester.search_books(test_query, max_results=1)
    if books:
        book = books[0]
        download_links = tester.test_download_links(book)
        for link in download_links:
            results['downloads'][link['type']] = link['valid']
    
    # Вывод итогового отчета
    tester.print_summary(results)

if __name__ == "__main__":
    main() 