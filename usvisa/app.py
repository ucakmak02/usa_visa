import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime

USEREMAIL = "email"
PASSWORD = "pass"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # or another port if required
EMAIL_USER = "email"
EMAIL_PASS = "pass"
RECIPIENT_EMAIL = "email"

async def main():
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://ais.usvisa-info.com/tr-tr/niv/users/sign_in")
            await asyncio.sleep(3)
            await page.get_by_label("E-posta *").click()
            await page.get_by_label("E-posta *").fill(USEREMAIL)
            await page.get_by_label("E-posta *").press("Tab")
            await page.get_by_label("Parola").fill(PASSWORD)
            await asyncio.sleep(5)
            await page.locator("label").filter(has_text="Gizlilik Politikasını ve").locator("div").click()
            await asyncio.sleep(5)
            await page.get_by_role("button", name="Oturum Aç").click()
            await asyncio.sleep(5)
            await page.wait_for_selector("img")

            mevcutrandevutarihi = await get_current_appointment_date(page)
            print(mevcutrandevutarihi)
            await asyncio.sleep(5)
            await page.locator('a[href="/tr-tr/niv/schedule/58434574/continue_actions"]').click()
            await asyncio.sleep(2)
            await page.get_by_role("tab", name=" Randevuyu Yeniden Zamanla").click()
            await asyncio.sleep(3)
            await page.get_by_role("link", name="Randevuyu Yeniden Zamanla").click()
            await asyncio.sleep(3)
            await page.locator('input[type="submit"][name="commit"][value="Devam Et"][class="button primary"]').click()
            await asyncio.sleep(3)
            await page.get_by_label("Randevu Tarihi *").click()
            await asyncio.sleep(3)

            buldugumtarih = await get_earliest_available_date(page)

            compare_dates_and_notify(mevcutrandevutarihi, buldugumtarih)

            await page.get_by_role("link", name="Eylemler").click()
            await page.get_by_role("link", name="Oturumu Kapat").click()

            await browser.close()
    except Exception as e:
        print(str(e))
        await browser.close()

async def get_current_appointment_date(page):
    new_html = await page.content()
    soup = BeautifulSoup(new_html, 'html.parser')

    given_str = soup.find('p', {'class': 'consular-appt'}).get_text().strip()

    date_str = given_str.split('\n')[1].strip().split(',')[0]
    year = given_str.split('\n')[1].strip().split(',')[1].strip()

    months = {
        'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4, 'Mayıs': 5, 'Haziran': 6,
        'Temmuz': 7, 'Ağustos': 8, 'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
    }

    date_parts = [part.strip() for part in date_str.split()]
    day = date_parts[0]
    month = date_parts[1]
    year = year

    return datetime(int(year), months[month], int(day))

async def get_earliest_available_date(page):
    new_html = await page.content()
    soup = BeautifulSoup(new_html, 'html.parser')

    div_element = soup.find('div', {'id': 'ui-datepicker-div'})

    td_elements = div_element.find_all('td', {'class': 'undefined'})

    filtered_elements = [td for td in td_elements if td.get('class') == ['undefined'] and 
                        td.get('data-event') == 'click' and 
                        td.get('data-handler') == 'selectDay']

    data_list = []

    for td in filtered_elements:
        date = td.find('a').get_text()
        month = td.get('data-month')
        if len(month) == 1:
            month = "0" + month
        else:
            None
        year = td.get('data-year')

        date_formatted = f"{date.zfill(2)}/{month}/{year}"

        data_list.append({"Date": date_formatted})

    df = pd.DataFrame(data_list)

    while df.empty:
        await page.get_by_title("Next").click()
        new_html = await page.content()
        soup = BeautifulSoup(new_html, 'html.parser')

        div_element = soup.find('div', {'id': 'ui-datepicker-div'})

        td_elements = div_element.find_all('td', {'class': 'undefined'})

        filtered_elements = [td for td in td_elements if td.get('class') == ['undefined'] and 
                            td.get('data-event') == 'click' and 
                            td.get('data-handler') == 'selectDay']

        data_list = []

        for td in filtered_elements:
            date = td.find('a').get_text()
            month = td.get('data-month')
            if len(month) == 1:
                month = "0" + month
            else:
                None
            year = td.get('data-year')

            date_formatted = f"{date.zfill(2)}/{month}/{year}"

            data_list.append({"Date": date_formatted})

            df = pd.DataFrame(data_list)

    buldugumtarih = df['Date'][0]
    return buldugumtarih

def compare_dates_and_notify(mevcutrandevutarihi, buldugumtarih):
    date1 = datetime.strptime(buldugumtarih, '%d/%m/%Y')
    date2 = mevcutrandevutarihi

    randtarihi = mevcutrandevutarihi.strftime('%d/%m/%Y')

    if date1 < date2:
        message = f"Daha erkene randevu buldum. {buldugumtarih} tarihine randevu acildi. Sizin guncel randevu tarihiniz : {randtarihi}"
        send_email_notification(message)
    else:
        print(f"En erken randevu tarihi {buldugumtarih}. Sizin randevu tarihiniz : {randtarihi}")

    

def send_email_notification(message):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = "USA Visa yeni randevu bulundu"

        body = MIMEText(message, 'plain')
        msg.attach(body)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    while True:
        asyncio.run(main())
