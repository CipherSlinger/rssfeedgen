import asyncio
from playwright.async_api import async_playwright
import re

async def auto_highlight_list(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # 注入更明显的高亮样式
        await page.add_style_tag(content="""
            .auto-highlight {
                border: 3px solid #ff0000 !important;
                box-shadow: 0 0 15px rgba(255,0,0,0.5) !important;
                transform: translateZ(0);
            }
        """)

        # 增强的智能选择逻辑
        await page.add_script_tag(content=r"""
            let lastHighlighted = null;
            let listContainer = null;
            const DATE_REGEX = /(\d{4}[-\/年]\d{1,2}[-\/月]\d{1,2})|(\d{1,2}[-\/月]\d{1,2}[-\/日]\d{4})/;

            function findListContainer(element) {
                let current = element;
                while (current) {
                    if (isListContainer(current)) return current;
                    current = current.parentElement;
                }
                return null;
            }

            function isListContainer(el) {
                // 优先检查ID特征
                if (/(list|container|wrap)/i.test(el.id)) return true;
                
                // 类名特征检测
                const listClasses = ['list', 'news-list', 'items', 'kjj_list'];
                if (listClasses.some(c => el.classList.contains(c))) return true;

                // 结构特征检测
                const children = el.children;
                if (children.length < 3) return false;
                
                let validCount = 0;
                for (let i = 0; i < Math.min(3, children.length); i++) {
                    const item = children[i];
                    if (item.querySelector('a') && DATE_REGEX.test(item.textContent)) {
                        validCount++;
                    }
                }
                return validCount >= 2;
            }

            function highlightContainer(element) {
                if (lastHighlighted) lastHighlighted.classList.remove('auto-highlight');
                element.classList.add('auto-highlight');
                lastHighlighted = element;
                listContainer = element;
            }

            // 优化的事件处理
            let debounceTimer;
            document.addEventListener('mousemove', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    const hovered = document.elementFromPoint(e.clientX, e.clientY);
                    const container = findListContainer(hovered);
                    container && highlightContainer(container);
                }, 100);
            });

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && listContainer) {
                    window.selectedListHTML = listContainer.outerHTML;
                    window.selectionConfirmed = true;
                }
            });

            function getRelativePath(element, container) {
                // If the element is the same as the container, return a self-selector
                if (element === container) return '';
                
                // Get the element's tag name
                let path = element.tagName.toLowerCase();
                
                // Add class if present
                if (element.className) {
                    const classes = element.className.split(' ')
                        .filter(c => c && !c.includes('active') && !c.includes('current') && !c.startsWith('on'))
                        .map(c => '.' + c);
                    if (classes.length) {
                        path += classes.join('');
                    }
                }
                
                // Add id if present and not dynamic
                if (element.id && !/\d/.test(element.id)) {
                    path = '#' + element.id;
                }
                
                // For common elements, just use the tag and distinguishing attributes
                if (element.tagName === 'A') {
                    return 'a';
                } else if (element.tagName === 'SPAN' && element.className.includes('time')) {
                    return 'span.time';
                } else if (element.tagName === 'TD' && element.cellIndex === 1) {
                    return 'td:nth-child(2)';
                }
                
                return path;
            }
        """)

        print("请移动鼠标到公告列表区域，按 Enter 确认提取...")
        
        try:
            await page.wait_for_function('window.selectionConfirmed === true', timeout=120000)
        except:
            print("操作超时")
            await browser.close()
            return
        
        # 增强的选择器推导
        selectors = await page.evaluate(r"""() => {
            const container = document.querySelector('.auto-highlight');
            if (!container) return null;

            // 获取容器选择器（优先ID）
            const getContainerSelector = (el) => {
                if (el.id) return `#${el.id}`;
                const classes = Array.from(el.classList).filter(c => !/^js-/.test(c));
                return classes.length > 0 ? `${el.tagName.toLowerCase()}.${classes.join('.')}` : el.tagName.toLowerCase();
            };

            // 获取元素层级路径
            const getCssPath = (el) => {
                const path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.tagName.toLowerCase();
                    if (el.id) {
                        selector += `#${el.id}`;
                        path.unshift(selector);
                        break;
                    } else {
                        const siblings = Array.from(el.parentNode.children);
                        const index = siblings.indexOf(el);
                        selector += `:nth-child(${index + 1})`;
                    }
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return path.join(' > ');
            };

            const items = Array.from(container.children).filter(el => {
                return el.querySelector('a') && DATE_REGEX.test(el.textContent);
            });

            // 推导各项选择器
            const getBestSelector = (elements, attr = '') => {
                if (elements.length === 0) return '';
    
                // 情况1：所有项都是同类型标签（如 li）
                const tagNames = elements.map(el => el.tagName.toLowerCase());
                if (new Set(tagNames).size === 1) {
                    return tagNames[0];
                }

                // 情况2：有共同类名（排除高亮类）
                const sampleClasses = Array.from(elements[0].classList).filter(c => c !== 'auto-highlight');
                const commonClasses = sampleClasses.filter(c => 
                    elements.every(el => el.classList.contains(c))
                );
                if (commonClasses.length > 0) {
                    return `${elements[0].tagName.toLowerCase()}.${commonClasses.join('.')}`;
                }

                // 情况3：返回直接子元素选择器（如 ul > li）
                return `${container.tagName.toLowerCase()} > ${elements[0].tagName.toLowerCase()}`;
            };

            const itemSelector = getBestSelector(items);
            
            // 获取链接和日期元素
            const sampleItem = items[0];
            const linkElement = sampleItem.querySelector('a');
            const dateElement = Array.from(sampleItem.childNodes).find(n => 
                DATE_REGEX.test(n.textContent)
            );

            return {
                container: getContainerSelector(container),
                item: itemSelector,
                title: linkElement ? getRelativePath(linkElement, container) : 'a',
                date: dateElement ? getRelativePath(dateElement, container) : '*',
                link: linkElement ? getRelativePath(linkElement, container) : 'a'

            };
        }""")

        if selectors:
            print("优化后的选择器：")
            print(f"容器：{selectors['container']}")
            print(f"列表项：{selectors['item']}")
            print(f"标题：{selectors['title']}")
            print(f"日期：{selectors['date']}")
            print(f"链接：{selectors['link']}")

            # 精确数据提取（限定容器范围）
            items = []
            container = await page.query_selector(selectors['container'])
            list_items = await container.query_selector_all(selectors['item'])
            print(f"找到 {len(list_items)} 个列表项")
            for list_item in list_items:
                # print(list_item)
                title_element = await list_item.query_selector(selectors['title'])
                link_element = await list_item.query_selector(selectors['link'])
                date_element = await list_item.query_selector(selectors['date'])
                
                title = await title_element.inner_text() if title_element else ""
                link = await link_element.get_attribute("href") if link_element else ""
                date = await date_element.inner_text() if date_element else ""
            
                items.append({"title": title.strip(), "link": link, "date": date.strip()})

            print("\nExtract Result：")
            # print(items)
            for item in items:
                print(f"Title: {item.get('title')}")
                print(f"Link: {item.get('link')}")
                print(f"Date: {item.get('date')}\n")
        else:
            print("未找到有效列表容器")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(auto_highlight_list(url='https://www.hp.gov.cn/gzhpkj/gkmlpt/index'))
    # https://kjj.gz.gov.cn/xxgk/zcfg/
    # https://gdstc.gd.gov.cn/zwgk_n/tzgg/
    # https://www.hp.gov.cn/gzhpkj/gkmlpt/index