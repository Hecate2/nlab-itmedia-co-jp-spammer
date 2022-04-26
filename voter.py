from typing import List, Tuple, Union
import asyncio
import re
import traceback
import psutil
import multiprocessing
from asyncio_pool import AioPool
import httpx
from playwright.async_api import Playwright, Browser, Page, Response
from decorators import AsyncRetry
from get_cf_clearance import (get_one_clearance, build_client_with_clearance,
    async_playwright, async_cf_retry, stealth_async)


def compute_browser_pool_size():
    total_memory = psutil.virtual_memory().total
    total_memory_GB = int(total_memory / 1024 ** 3)
    return int((total_memory_GB - 3) / (multiprocessing.cpu_count() * 0.25))


# proxy_source = 'https://spys.one/free-proxy-list/JP/'
proxy_source = 'http://tiqu.py.cn/getProxyIp?protocol=http&num=1&regions=jp&lb=1&return_type=txt'
vote_url = 'https://nlab.itmedia.co.jp/research/articles/676476/vote/'
browser_pool_size = compute_browser_pool_size()
worker_loop = asyncio.get_event_loop()
asyncio.set_event_loop(worker_loop)
playwright: Playwright = worker_loop.run_until_complete(async_playwright().start())
httpx_client = httpx.AsyncClient(verify=False)

browser_args = [
    # "https://peter.sh/experiments/chromium-command-line-switches/"
    "--enable-low-end-device-mode",
    "--no-sandbox",
    "--single-process",
    "--renderer-process-limit=1",
    "--disable-smooth-scrolling",
    "--disable-web-security",
    # "--disable-webgl",
    "--disable-dev-shm-usage",
    "--disable-site-isolation-trials",
    "--disable-features=site-per-process",
]
page_args = {'viewport': {"width": 0, "height": 0}}


@AsyncRetry.retry(retries=3)
async def get_proxies(page: Page):
    await page.goto(proxy_source)
    res: bool = await async_cf_retry(page)
    if res:
        content = await page.content()
        proxies: List[Tuple[str]] = re.findall(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?(:\d{1,5})</font>.*?(HTTP|SOCKS\d)</font>", content)
        proxies: List[str] = [f'{proxy[2].lower()}://{proxy[0]}{proxy[1]}' for proxy in proxies]
        return proxies
    raise Exception('Failed to penetrate cloudflare')


async def proxy_generator():
    # browser: Browser = await playwright.chromium.launch(
    #     headless=False, args=browser_args)
    # context = await browser.new_context(**page_args)
    # page = await context.new_page()
    # await stealth_async(page)
    while 1:
        try:
            # for proxy in await get_proxies(page):
            # for proxy in ['http://45.77.31.181:8181', 'http://45.77.31.181:80', 'http://160.251.14.122:3129', 'http://5.188.71.188:9977', 'http://5.188.71.186:23456', 'http://140.227.25.56:5678', 'http://52.197.187.140:443', 'http://153.122.107.129:80', 'http://153.122.106.94:80', 'http://168.138.211.5:8080', 'http://168.138.211.5:49995', 'http://140.83.32.175:3128', 'http://168.138.41.227:8118', 'http://168.138.41.227:80', 'http://133.125.54.107:80', 'http://140.227.127.228:80', 'http://140.227.211.47:8080', 'http://13.114.160.78:80', 'http://153.122.86.46:80', 'http://172.104.84.161:80', 'http://133.242.146.103:8000', 'http://172.105.197.49:80', 'http://54.168.230.235:8080', 'http://13.230.192.123:8080', 'http://160.251.97.210:3128', 'http://139.162.77.39:7761', 'http://160.16.142.244:3128', 'http://92.38.178.130:8080', 'http://172.104.84.161:443']:
            # for proxy in ['http://5.188.71.188:9977', 'http://13.230.168.82:3128', 'http://106.158.156.213:80']:
            # for proxy in ['http://localhost:8888']:
            for proxy in (await httpx_client.get(proxy_source)).text.split('\r\n'):
                print(proxy)
                if not proxy:
                    await asyncio.sleep(2)
                    continue
                yield proxy if proxy.startswith('http://') else f'http://{proxy}'
        except:
            await asyncio.sleep(10)


def save_vote_success_record(proxy: str):
    print(f'vote success: {proxy}')
    with open('vote_success.txt', 'a') as f:
        f.write(f'{proxy}\n')


def save_net_failure_record(proxy: str):
    with open('net_failure.txt', 'a') as f:
        f.write(f'{proxy}\n')


def save_vote_failure_record(proxy: str):
    with open('vote_failure.txt', 'a') as f:
        f.write(f'{proxy}\n')


async def vote(proxy: str):
    if proxy:
        browser: Browser = await playwright.chromium.launch(
            headless=False, proxy={"server": "per-context"}, args=browser_args)
    else:
        browser: Browser = await playwright.chromium.launch(
            headless=False, args=browser_args)
    context = await browser.new_context(proxy={"server": proxy})#, **page_args)
    context.set_default_navigation_timeout(300000)
    page = await context.new_page()
    await stealth_async(page)
    try:
        await page.route(lambda s: 'itmedia.co.jp' not in s, lambda route: route.abort())
        await page.route(lambda s: '.css' in s, lambda route: route.abort())
        await page.evaluate(f'''window.location.href="{vote_url}"''')
        # content = await page.content()
        # if content == '':
        #     raise Exception('No content')
        if page.url != vote_url:
            raise Exception('Network failure')

        async with page.expect_response("https://nlab.itmedia.co.jp/research/assets/js/bundle.js*", timeout=30 * 1000) as waiter:
            await page.locator('''label:has-text("終末なにしてますか? 忙しいですか? 救ってもらっていいですか?")''').click()
        async with page.expect_response("https://api.nlab.itmedia.co.jp/api.php", timeout=300*1000) as response_info:
            await page.route(lambda s: 'https://api.nlab.itmedia.co.jp/api.php' not in s, lambda route: route.abort())
            await page.locator('id=js-addVote').click()
        response = await response_info.value
        if response.status >= 400:
            save_vote_failure_record(proxy)
        else:
            save_vote_success_record(proxy)
    except:
        save_net_failure_record(proxy)
        traceback.print_exc()
    finally:
        await browser.close()


@AsyncRetry.retry(retries=3)
async def main():
    proxy_gen = proxy_generator()
    pool = AioPool(1)#browser_pool_size)
    while 1:
        proxy = await proxy_gen.__anext__()
        await pool.spawn(vote(proxy))
        print(proxy)


worker_loop.run_until_complete(main())
worker_loop.run_forever()
