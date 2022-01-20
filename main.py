from __future__ import print_function, absolute_import, unicode_literals

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from requests.api import get
from bs4 import BeautifulSoup
from os import environ

from time import sleep
from json import dumps, loads

from pymongo.mongo_client import MongoClient
from bson.objectid import ObjectId

database_client = MongoClient(environ.get("mongo_url"))["youtube"]["last"]

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

class CurrentCovidStatusResultReturn:
    def __init__(self, current, new, severe, dead, total, total_dead) -> None:
        self.current = current
        self.new = new
        self.severe = severe
        self.total = total.replace("(누적)확진", "").replace("다운로드", "")
        self.total_dead = total_dead.replace("(누적)사망", "")
        self.dead = dead

def GetCurrentKoreaCovidStatus() -> CurrentCovidStatusResultReturn:
    response = get("http://ncov.mohw.go.kr/")

    soup = BeautifulSoup(response.text, "html.parser")

    current = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_graph > table > tbody > tr:nth-child(1) > td:nth-child(5) > span").get_text()
    new = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_graph > table > tbody > tr:nth-child(1) > td:nth-child(4) > span").get_text()
    severe = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_graph > table > tbody > tr:nth-child(1) > td:nth-child(3) > span").get_text()
    dead = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_graph > table > tbody > tr:nth-child(1) > td:nth-child(2) > span").get_text()
    total = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_num > div:nth-child(2)").get_text()
    total_dead = soup.select_one("#content > div > div > div.liveboard_layout > div.liveToggleOuter > div > div.live_left > div.occurrenceStatus > div.occur_num > div:nth-child(1)").get_text()

    return CurrentCovidStatusResultReturn(current, new, severe, dead, total, total_dead)

def ChangeVideoDescriptionToCovidDescription(id, status: CurrentCovidStatusResultReturn):
    global SCOPES, database_client
    _title = "이 영상의 설명은 오늘의 코로나 확진자 수 입니다."
    _description = (
        f"누적 코로나 확진자 수: {status.total}",
        f"확진자 수: {status.current}",
        f"신규 확진자 수: {status.new}",
        f"위중증 환자 수: {status.severe}",
        f"사망자 수: {status.dead}",
        f"누적 사망자 수: {status.total_dead}"
    )
    _credentials = Credentials.from_authorized_user_info(loads(database_client.find_one({"_id": ObjectId("61e9727070aa69642863a4bf")})["credential"]))
    
    if not _credentials.valid:
        _credentials.refresh(Request())
        print(_credentials)
    database_client.update_one({"_id": ObjectId("61e9727070aa69642863a4bf")}, {"$set": {"credential": str(_credentials.to_json())}})

    _youtube = build("youtube", "v3", credentials=_credentials)
    _request = _youtube.videos().update(
        part="snippet",
        body={
            "id": id,
            "snippet": {
                "categoryId": 22,
                "description": "\n".join(_description),
                "tags": ["covid", "covid-19"],
                "title": _title
            }
        }
    )
    response = _request.execute()
    print("Response: " + dumps(response))

def ChangeVideoDescriptionWorker():
    def ChangeVideoDescriptionProcess() -> None:
        while True:
            current_covid_status = GetCurrentKoreaCovidStatus()
            ChangeVideoDescriptionToCovidDescription(environ.get("video_id"), current_covid_status)
            sleep(3600)

    ChangeVideoDescriptionWorker.run = ChangeVideoDescriptionProcess()
    return ChangeVideoDescriptionWorker

if __name__ == "__main__": ChangeVideoDescriptionWorker().run
