import json
from types import SimpleNamespace
import networkx as nx
import pytest
import requests
from shapely.geometry import box,mapping
from engine import cobertura as c

def test_switches_to_another_real_osm_endpoint_and_restores_settings(monkeypatch):
    original={'headers':{'X-Test':'value'}}
    settings=SimpleNamespace(overpass_url='original',requests_kwargs=original)
    calls=[];probes=[];graph=nx.MultiDiGraph()
    def download(*args,**kwargs):
        calls.append(settings.overpass_url)
        if len(calls)==1:raise requests.ConnectTimeout('simulated blocked endpoint')
        assert settings.requests_kwargs['hooks']['response'][0] is c._fail_retryable_response
        return graph
    ox=SimpleNamespace(settings=settings,graph_from_polygon=download)
    monkeypatch.setattr(c,'_probe_endpoint',probes.append)
    result=c._download(ox,box(0,0,1,1),lambda message:None)
    assert result is graph and calls==list(c.OVERPASS_ENDPOINTS) and probes==list(c.OVERPASS_ENDPOINTS)
    assert settings.overpass_url=='original' and settings.requests_kwargs is original

def test_probe_failure_skips_endpoint_without_waiting_for_full_download(monkeypatch):
    settings=SimpleNamespace(overpass_url='original',requests_kwargs={});calls=[]
    def probe(url):
        if url==c.OVERPASS_ENDPOINTS[0]:raise requests.ConnectTimeout('5 seconds bounded')
    def download(*args,**kwargs):calls.append(settings.overpass_url);return nx.MultiDiGraph()
    monkeypatch.setattr(c,'_probe_endpoint',probe)
    c._download(SimpleNamespace(settings=settings,graph_from_polygon=download),None,lambda m:None)
    assert calls==[c.OVERPASS_ENDPOINTS[1]]

def test_all_endpoints_fail_with_friendly_retryable_details_and_no_synthetic_fallback(monkeypatch):
    settings=SimpleNamespace(overpass_url='original',requests_kwargs={})
    def fail(url):raise requests.ConnectTimeout('internal technical detail')
    monkeypatch.setattr(c,'_probe_endpoint',fail)
    with pytest.raises(c.OSMDownloadError) as error:
        c._download(SimpleNamespace(settings=settings),None,lambda m:None)
    assert len(error.value.attempts)==2 and 'ConnectTimeout' not in str(error.value)
    assert 'No es un fallo de QAOA' in str(error.value)
    assert settings.overpass_url=='original'

def test_busy_response_stops_recursive_osmnx_retry():
    response=requests.Response();response.status_code=504;response.url='https://example.test/api/interpreter'
    with pytest.raises(requests.HTTPError):c._fail_retryable_response(response)

def test_cache_reuse_requires_full_polygon_coverage(tmp_path):
    graph=tmp_path/'coverage_large.graphml';graph.write_text('graph')
    manifest=tmp_path/'coverage_large.coverage.json'
    manifest.write_text(json.dumps({'policy':c.POLICY,'graph_file':graph.name,'polygon':mapping(box(0,0,10,10))}))
    assert c._covering_cache(tmp_path,box(2,2,3,3))==graph
    assert c._covering_cache(tmp_path,box(9,9,11,11)) is None
