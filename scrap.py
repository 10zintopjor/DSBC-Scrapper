from cgitb import text
from multiprocessing.sharedctypes import Value
from operator import truediv
from openpecha.core.pecha import OpenPechaFS
from openpecha.core.ids import get_pecha_id
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum,PechaMetaData
from urllib import request
from datetime import datetime
from pyparsing import srange
from requests_html import HTMLSession
from openpecha import config
import os
 
start_url ='http://www.dsbcproject.org/canon-text/bibliography'

def make_request(url):
    s=HTMLSession()
    response =s.get(url)
    return response

def get_page(url):
    response = make_request(url)
    pechas = response.html.find('h5 a')
    titles = response.html.find('div.title-tag li div.hours')
    dic = {}

    for pecha in pechas:
        dic.update({pecha.text:pecha.attrs['href']})

    try:
        nxt = response.html.find('ul.pagination li a[rel="next"]',first = True)
        nxt_link = nxt.attrs['href']
        new_dic = get_page(start_url+nxt_link)
        dic.update(new_dic)
        return dic
    except:
        return dic


def parse_page(response):
    
    base_text = {}
    book_meta={}
    src_meta={}
    books = response.html.find('table#customers a')

    for book in books:
        book_page = make_request(book.attrs["href"])
        text = book_page.html.find('div.news-section',first = True).text
        h_section = book_page.html.find('div.news-section ul.breadcrumbs,h3,h3+h5,div.title-info')
        text_name = book_page.html.find('div.news-section h3',first=True).text
        for h in h_section:
            text = text.replace(h.text,"").strip("\n\n")
        base_text.update({text_name:text})
        meta = get_meta(book_page)
        book_meta.update({text_name:meta})

    src_meta = get_meta(response)
    src_meta.update(book_meta)
    opf_path=create_opf(base_text,src_meta)
    write_readme(src_meta,opf_path)

def get_meta(page):
    src_meta = {}
    book_key = page.html.find('div.title-info li span')
    book_value = page.html.find('div.title-info li div')

    for key,value in zip(book_key,book_value):
        src_meta.update({key.text.replace(":",""):value.text})

    return src_meta

def create_opf(base_text,src_meta):
    opf_path="./opfs"
    instance_meta = PechaMetaData(
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata=src_meta)

    opf = OpenPechaFS(
        meta=instance_meta,
        base=base_text
        )

    opf_path = opf.save(output_path=opf_path)
    return opf_path


def get_pecha(url):
    try:
        response = make_request(url)
        parse_page(response)
    except:
        print("passing")
        pass

def create_readme(source_metadata):

    Table = "| --- | --- "
    Title = f"|Title | {source_metadata['Title']} "
    lang = f"|Editor | {source_metadata['Editor']}"
    publisher = f"|Publisher | {source_metadata['Publisher']}"
    year = f"|Year | {source_metadata['Year']}"


    readme = f"{Title}\n{Table}\n{lang}\n{publisher}\n{year}~`"
    return readme

def write_readme(src_meta,opf_path):
    readme = create_readme(src_meta)
    path_parent = os.path.dirname(opf_path)
    with open(f"{path_parent}/readme.md","w") as f:
        f.write(readme)

if __name__ == "__main__":
    dics = get_page(start_url)
    #get_pecha('http://www.dsbcproject.org/canon-text/book/7')

    for dic in dics.values():
        get_pecha(dic)
        

