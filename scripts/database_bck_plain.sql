--
-- PostgreSQL database dump
--

-- Dumped from database version 9.4.4
-- Dumped by pg_dump version 9.4.4
-- Started on 2017-10-16 13:33:08

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- TOC entry 173 (class 3079 OID 11855)
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- TOC entry 1998 (class 0 OID 0)
-- Dependencies: 173
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- TOC entry 172 (class 1259 OID 484172)
-- Name: products; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE products (
    name character varying(50),
    id bigint NOT NULL,
    registered timestamp with time zone,
    modified timestamp with time zone,
    expiration_date timestamp with time zone,
    quantity double precision
);


ALTER TABLE products OWNER TO postgres;

--
-- TOC entry 1990 (class 0 OID 484172)
-- Dependencies: 172
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY products (name, id, registered, modified, expiration_date, quantity) FROM stdin;
olives	5	2017-10-01 01:21:36.914+02	2017-10-01 01:21:36.914+02	2017-10-18 01:21:36.738+02	150
ketchup	6	2017-10-01 01:21:36.937+02	2017-10-01 01:21:36.937+02	2017-10-18 01:21:36.738+02	100
ham	7	2017-10-01 01:21:36.961+02	2017-10-01 01:21:36.961+02	2017-10-18 01:21:36.738+02	250
cream	9	2017-10-01 01:21:37.009+02	2017-10-01 01:21:37.009+02	2017-10-19 01:21:36.738+02	80
cheese	8	2017-10-01 01:21:36.984+02	2017-10-01 01:21:36.984+02	2017-10-18 01:21:36.738+02	120
york ham	11	2017-10-01 01:21:37.059+02	2017-10-01 01:21:37.059+02	2017-10-19 01:21:36.738+02	200
juice	10	2017-10-01 01:21:37.035+02	2017-10-01 01:21:37.035+02	2017-10-19 01:21:36.738+02	50
tomatoes	12	2017-10-01 01:21:37.092+02	2017-10-01 01:21:37.092+02	2017-10-19 01:21:36.738+02	1000
eggplant	13	2017-10-01 01:21:37.125+02	2017-10-01 01:21:37.125+02	2017-10-20 01:21:36.738+02	500
beer	14	2017-10-01 01:21:37.149+02	2017-10-01 01:21:37.149+02	2017-10-20 01:21:36.738+02	400
coke	15	2017-10-01 01:21:37.172+02	2017-10-01 01:21:37.172+02	2017-10-20 01:21:36.738+02	200
apple	16	2017-10-01 01:21:37.196+02	2017-10-01 01:21:37.196+02	2017-10-20 01:21:36.738+02	500
plum	17	2017-10-01 01:21:37.224+02	2017-10-01 01:21:37.224+02	2017-10-21 01:21:36.738+02	400
orange	18	2017-10-01 01:21:37.248+02	2017-10-01 01:21:37.248+02	2017-10-21 01:21:36.738+02	1500
cucumber	19	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-21 01:21:36.738+02	500
pepper	20	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-21 01:21:36.738+02	10
chicken	21	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-21 01:21:36.738+02	900
salmon	22	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-22 01:21:36.738+02	500
butter	23	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-22 01:21:36.738+02	50
eggs	24	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-22 01:21:36.738+02	300
carrot	25	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-22 01:21:36.738+02	600
onion	1	2017-10-01 01:21:36.738+02	2017-10-01 01:21:36.738+02	2017-10-18 01:21:36.738+02	230
lettuce	2	2017-10-01 01:21:36.843+02	2017-10-01 01:21:36.843+02	2017-10-18 01:21:36.738+02	158
milk	3	2017-10-01 01:21:36.867+02	2017-10-01 01:21:36.867+02	2017-10-18 01:21:36.738+02	100
mayonnaise	4	2017-10-01 01:21:36.891+02	2017-10-01 01:21:36.891+02	2017-10-18 01:21:36.738+02	150
zucchini	26	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-22 01:21:36.738+02	500
garlic	27	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-30 00:21:36.738+01	20
mushroom	28	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-30 00:21:36.738+01	500
banana	29	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-30 00:21:36.738+01	700
spinach	30	2017-10-01 01:21:37.272+02	2017-10-01 01:21:37.272+02	2017-10-30 00:21:36.738+01	360
\.


--
-- TOC entry 1880 (class 2606 OID 484180)
-- Name: products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres; Tablespace: 
--

ALTER TABLE ONLY products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- TOC entry 1997 (class 0 OID 0)
-- Dependencies: 5
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


-- Completed on 2017-10-16 13:33:09

--
-- PostgreSQL database dump complete
--

