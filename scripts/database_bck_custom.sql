PGDMP     #    !            	    u           smartfridge    9.4.4    9.4.4     �           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                       false            �           0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                       false            �           1262    484171    smartfridge    DATABASE     �   CREATE DATABASE smartfridge WITH TEMPLATE = template0 ENCODING = 'UTF8' LC_COLLATE = 'Spanish_Spain.1252' LC_CTYPE = 'Spanish_Spain.1252';
    DROP DATABASE smartfridge;
             postgres    false                        2615    2200    public    SCHEMA        CREATE SCHEMA public;
    DROP SCHEMA public;
             postgres    false            �           0    0    SCHEMA public    COMMENT     6   COMMENT ON SCHEMA public IS 'standard public schema';
                  postgres    false    5            �           0    0    public    ACL     �   REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;
                  postgres    false    5            �            3079    11855    plpgsql 	   EXTENSION     ?   CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;
    DROP EXTENSION plpgsql;
                  false            �           0    0    EXTENSION plpgsql    COMMENT     @   COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';
                       false    173            �            1259    484172    products    TABLE     �   CREATE TABLE products (
    name character varying(50),
    id bigint NOT NULL,
    registered timestamp with time zone,
    modified timestamp with time zone,
    expiration_date timestamp with time zone,
    quantity double precision
);
    DROP TABLE public.products;
       public         postgres    false    5            �          0    484172    products 
   TABLE DATA               V   COPY products (name, id, registered, modified, expiration_date, quantity) FROM stdin;
    public       postgres    false    172   
       X           2606    484180    products_pkey 
   CONSTRAINT     M   ALTER TABLE ONLY products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);
 @   ALTER TABLE ONLY public.products DROP CONSTRAINT products_pkey;
       public         postgres    false    172    172            �     x����n�0D��W�>HC���[rQ��x��%@���eb7�n�A�L�Xež���(��<x2���b�K���HP��J[%	r����f�T�3l)���7F7nP%��D�^b�H��9�f�Ř���HP��+b7!,AU�x��yu�s4�3��Sr�1����M������@����������5n��� @j�{�����שw���@���~aV��L4� 1���>v�=W"��7����u���K+!�B��%����h)���Da�o$֗8��J�s�"FV�����!�7�o�`�N@����<�˝0M�G>V��*��]�p
_���H��?ᑏԶ��>�'��|`O�mZ7�q�o��㋴�cK�s��-�w%�#h��ún��<�ʬ�?H����C�w�;R��� 	W��}�qt-}g��%L-��p���yJ��*�����_�ܷ^�И�-ձ��Oۢ�mi��Be��e֍�Sx�/|�gjG�����ma��Ek�'1m     