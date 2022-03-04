from cgitb import text
from curses import flash
from email.mime import base
from hashlib import new
from posixpath import splitext
from pydoc import pager
from uuid import uuid4
from openpecha.core.pecha import OpenPechaFS
from openpecha.core.ids import get_pecha_id
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum,PechaMetaData
from openpecha.core.annotation import Page, Span
from urllib import request
from datetime import datetime
from pyparsing import srange
from requests_html import HTMLSession
from openpecha import github_utils,config
from pathlib import Path
import os
import re
import itertools
 
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
        text = get_img_num(text)     
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

    text,has_layer = to_base_text_format(base_text)
    opf = OpenPechaFS(
        meta=instance_meta,
        base=text,
        layers = get_layers(base_text) if has_layer else {}
        )    
    opf_path = opf.save(output_path=opf_path)
    return opf_path


def get_layers(base_text):
    layers ={}

    for text_name in base_text:
        text_list = base_text[text_name]
        layers[text_name] = {
            LayerEnum.pagination:get_sub_text_pagination(text_list)
        }

    return layers


def get_sub_text_pagination(text_list):
    page_annotations={}
    char_walker = 0
    for elem in text_list:
        page_annotation,char_walker = get_page_annotation(elem,char_walker)
        page_annotations.update(page_annotation)

    pagination_layer = Layer(
        annotation_type=LayerEnum.pagination,annotations=page_annotations
    ) 

    return pagination_layer

def get_page_annotation(elem,char_walker):
    page_start = char_walker
    page_end = char_walker + len(elem['text']) 
    if elem['imgnum']:
        page_annotation = {
            uuid4().hex:Page(span=Span(start = page_start,end =page_end),imgnum=elem['imgnum'])
        }
    else:
        page_annotation = {
            uuid4().hex:Page(span=Span(start = page_start,end =page_end))
        }

    return page_annotation,page_end+2


def to_base_text_format(texts):
    base_txt = {}
    for text_name in texts:
        str_text = ""
        text_list  = texts[text_name]
        if not isinstance(text_list,list):
            return texts,False
        for elm in text_list:
            str_text += elm['text']+"\n\n"

        base_txt.update({text_name:str_text})

    return base_txt,True


def append_imgnum(re_pattern,text):
    base_text = []
    splitted_text = re.split(re_pattern,text)
    imgnums = re.findall(re_pattern,text)
    for text,imgnum in itertools.zip_longest(splitted_text,imgnums):
        text = remove_double_linebreak(text)
        if imgnum != None:
            imgnum = re.search("\d+",imgnum).group()
        text = change_text_format(text)    
        base_text.append({"imgnum":imgnum,"text":text})

    return base_text

def get_img_num(text):
    base_text = []
    if re.search("\|\|\d+\|\|\n\n\n",text):
        re_pattern = "\|\|\d+\|\|"
        base_text = append_imgnum(re_pattern,text)  
    elif re.search("\[\d+\]\n\n",text):
        re_pattern = "\[\d+\]"
        base_text = append_imgnum(re_pattern,text)
    else:
        return text

    return base_text
                

def remove_double_linebreak(text):
    prev = ""
    new_text = ""

    for i in range(len(text)):
        if text[i] == "\n" and prev == "\n":
            continue
        new_text += text[i]
        prev = text[i]

    return new_text.strip()


def get_pecha(url):
    """ try:
        response = make_request(url)
    except:
        print("passing") """

    response = make_request(url)

    parse_page(response)

def create_readme(source_metadata):

    Table = "| --- | --- "
    Title = f"|Title | {source_metadata['Title']} "
    lang = f"|Editor | {source_metadata['Editor']}"
    publisher = f"|Publisher | {source_metadata['Publisher']}"
    year = f"|Year | {source_metadata['Year']}"


    readme = f"{Title}\n{Table}\n{lang}\n{publisher}\n{year}~`"
    return readme


def change_text_format(text):
    base_text=""
    prev= ""
    text = text.replace("\n","") 
    ranges = iter(range(len(text)))
    for i in ranges:
        if i<len(text)-1:
            if i%90 == 0 and i != 0 and re.search("\s",text[i+1]):
                base_text+=text[i]+"\n"
            elif i%90 == 0 and i != 0 and re.search("\S",text[i+1]):
                while i < len(text)-1 and re.search("\S",text[i+1]):
                    base_text+=text[i]
                    i = next(ranges) 
                base_text+=text[i]+"\n" 
            elif prev == "\n" and re.search("\s",text[i]):
                continue
            else:
                base_text+=text[i]
        else:
            base_text+=text[i]
        prev = base_text[-1]
    return base_text

def write_readme(src_meta,opf_path):
    readme = create_readme(src_meta)
    path_parent = os.path.dirname(opf_path)
    with open(f"{path_parent}/readme.md","w") as f:
        f.write(readme)


def publish_pecha(opf_path):
    github_utils.github_publish(
    opf_path,
    not_includes=[],
    message="initial commit"
    )


def main():
    #dics = get_page(start_url)
    get_pecha('http://www.dsbcproject.org/canon-text/book/18')
    """ for dic in dics.values():
        get_pecha(dic) """


if __name__ == "__main__":
    main()
    
        

