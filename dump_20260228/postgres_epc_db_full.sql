--
-- PostgreSQL database dump
--

\restrict 6JnMwKTpURvhwofjqwSBTbnZGYVXehHF5d6A8IlaLfZDoJEs3YoqeF82kSMsy9l

-- Dumped from database version 15.15
-- Dumped by pg_dump version 15.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP POLICY IF EXISTS rls_users_tenant ON public.users;
DROP POLICY IF EXISTS rls_patients_tenant ON public.patients;
DROP POLICY IF EXISTS rls_abac_policies_tenant ON public.abac_policies;
DROP POLICY IF EXISTS rls_abac_audit_tenant ON public.abac_audit_log;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tenant_api_keys DROP CONSTRAINT IF EXISTS tenant_api_keys_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.patients DROP CONSTRAINT IF EXISTS patients_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.patient_status DROP CONSTRAINT IF EXISTS patient_status_patient_id_fkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_patient_id_fkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_last_edited_by_fkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_admission_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branding DROP CONSTRAINT IF EXISTS branding_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.admissions DROP CONSTRAINT IF EXISTS admissions_tenant_id_fkey;
ALTER TABLE IF EXISTS ONLY public.admissions DROP CONSTRAINT IF EXISTS admissions_patient_id_fkey;
DROP INDEX IF EXISTS public.ix_abac_audit_log_trace_id;
DROP INDEX IF EXISTS public.ix_abac_audit_log_tenant_id;
DROP INDEX IF EXISTS public.ix_abac_audit_log_created_at;
DROP INDEX IF EXISTS public.idx_users_tenant_id;
DROP INDEX IF EXISTS public.idx_patients_tenant_id;
DROP INDEX IF EXISTS public.idx_abac_policies_tenant_name_active;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_username_key;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_email_key;
ALTER TABLE IF EXISTS ONLY public.tenants DROP CONSTRAINT IF EXISTS tenants_pkey;
ALTER TABLE IF EXISTS ONLY public.tenants DROP CONSTRAINT IF EXISTS tenants_code_key;
ALTER TABLE IF EXISTS ONLY public.tenant_api_keys DROP CONSTRAINT IF EXISTS tenant_api_keys_pkey;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_pkey;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_name_key;
ALTER TABLE IF EXISTS ONLY public.patients DROP CONSTRAINT IF EXISTS patients_pkey;
ALTER TABLE IF EXISTS ONLY public.patient_status DROP CONSTRAINT IF EXISTS patient_status_pkey;
ALTER TABLE IF EXISTS ONLY public.epc DROP CONSTRAINT IF EXISTS epc_pkey;
ALTER TABLE IF EXISTS ONLY public.epc_events DROP CONSTRAINT IF EXISTS epc_events_pkey;
ALTER TABLE IF EXISTS ONLY public.branding DROP CONSTRAINT IF EXISTS branding_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS ONLY public.admissions DROP CONSTRAINT IF EXISTS admissions_pkey;
ALTER TABLE IF EXISTS ONLY public.abac_policies DROP CONSTRAINT IF EXISTS abac_policies_pkey;
ALTER TABLE IF EXISTS ONLY public.abac_audit_log DROP CONSTRAINT IF EXISTS abac_audit_log_pkey;
ALTER TABLE IF EXISTS public.roles ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.epc_events ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.branding ALTER COLUMN id DROP DEFAULT;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.tenants;
DROP TABLE IF EXISTS public.tenant_api_keys;
DROP SEQUENCE IF EXISTS public.roles_id_seq;
DROP TABLE IF EXISTS public.roles;
DROP TABLE IF EXISTS public.patients;
DROP TABLE IF EXISTS public.patient_status;
DROP SEQUENCE IF EXISTS public.epc_events_id_seq;
DROP TABLE IF EXISTS public.epc_events;
DROP TABLE IF EXISTS public.epc;
DROP SEQUENCE IF EXISTS public.branding_id_seq;
DROP TABLE IF EXISTS public.branding;
DROP TABLE IF EXISTS public.alembic_version;
DROP TABLE IF EXISTS public.admissions;
DROP TABLE IF EXISTS public.abac_policies;
DROP TABLE IF EXISTS public.abac_audit_log;
-- *not* dropping schema, since initdb creates it
--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: abac_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.abac_audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trace_id character varying(64) NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    action character varying(100) NOT NULL,
    resource_type character varying(100) NOT NULL,
    resource_id character varying(255),
    effect character varying(10) NOT NULL,
    matched_rules jsonb NOT NULL,
    policy_version integer NOT NULL,
    context jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: abac_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.abac_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid,
    name character varying(255) NOT NULL,
    version integer NOT NULL,
    is_active boolean NOT NULL,
    strategy character varying(50) NOT NULL,
    default_effect character varying(10) NOT NULL,
    rules jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by uuid
);


--
-- Name: admissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    sector character varying(120),
    habitacion character varying(40),
    cama character varying(40),
    fecha_ingreso timestamp without time zone NOT NULL,
    fecha_egreso timestamp without time zone,
    protocolo character varying(60),
    admision_num character varying(60),
    estado character varying(30) DEFAULT 'internacion'::character varying NOT NULL,
    tenant_id character varying(36)
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: branding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.branding (
    id integer NOT NULL,
    hospital_nombre character varying(160),
    logo_url character varying(255),
    header_linea1 character varying(255),
    header_linea2 character varying(255),
    footer_linea1 character varying(255),
    footer_linea2 character varying(255),
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    tenant_id character varying(36)
);


--
-- Name: branding_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.branding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: branding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.branding_id_seq OWNED BY public.branding.id;


--
-- Name: epc; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epc (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    admission_id character varying(36),
    estado character varying(20) NOT NULL,
    version_actual_oid character varying(64),
    titulo character varying(255),
    diagnostico_principal_cie10 character varying(15),
    fecha_emision timestamp without time zone,
    medico_responsable character varying(120),
    firmado_por_medico boolean,
    created_by character varying(36) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    motivo_internacion text,
    evolucion text,
    procedimientos text,
    interconsultas text,
    medicacion text,
    indicaciones_alta text,
    recomendaciones text,
    last_edited_by character varying(36),
    last_edited_at timestamp without time zone,
    has_manual_changes boolean,
    regenerated_count integer DEFAULT 0 NOT NULL,
    tenant_id character varying(36)
);


--
-- Name: epc_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epc_events (
    id integer NOT NULL,
    epc_id character varying(36) NOT NULL,
    at timestamp without time zone DEFAULT now() NOT NULL,
    by character varying(120),
    action text NOT NULL
);


--
-- Name: epc_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.epc_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: epc_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.epc_events_id_seq OWNED BY public.epc_events.id;


--
-- Name: patient_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_status (
    patient_id character varying(36) NOT NULL,
    estado character varying(20) NOT NULL,
    observaciones text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    id character varying(36) NOT NULL,
    dni character varying(20),
    cuil character varying(20),
    obra_social character varying(80),
    nro_beneficiario character varying(50),
    apellido character varying(80) NOT NULL,
    nombre character varying(80) NOT NULL,
    fecha_nacimiento character varying(10),
    sexo character varying(10),
    estado character varying(30) DEFAULT 'internacion'::character varying NOT NULL,
    telefono character varying(40),
    email character varying(120),
    domicilio text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    tenant_id character varying(36)
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(20) NOT NULL
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: tenant_api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_api_keys (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    key_hash character varying(255) NOT NULL,
    key_prefix character varying(8),
    name character varying(80),
    is_active boolean,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    last_used_at timestamp without time zone,
    expires_at timestamp without time zone
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id character varying(36) NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(160) NOT NULL,
    logo_url character varying(255),
    contact_email character varying(120),
    is_active boolean,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    webhook_url character varying(512),
    api_rate_limit integer,
    integration_type character varying(20) DEFAULT 'inbound'::character varying NOT NULL,
    external_endpoint character varying(512),
    external_token character varying(512),
    external_auth_type character varying(20) DEFAULT 'bearer'::character varying,
    external_headers text,
    allowed_scopes character varying(512) DEFAULT 'read_patients,read_epc'::character varying,
    webhook_secret character varying(255),
    notes text,
    display_rules text DEFAULT '{}'::text
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    username character varying(80) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(120) NOT NULL,
    email character varying(120),
    role_id integer NOT NULL,
    is_active boolean,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    tenant_id character varying(36)
);


--
-- Name: branding id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branding ALTER COLUMN id SET DEFAULT nextval('public.branding_id_seq'::regclass);


--
-- Name: epc_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc_events ALTER COLUMN id SET DEFAULT nextval('public.epc_events_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Data for Name: abac_audit_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.abac_audit_log (id, trace_id, tenant_id, user_id, action, resource_type, resource_id, effect, matched_rules, policy_version, context, created_at) FROM stdin;
\.


--
-- Data for Name: abac_policies; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.abac_policies (id, tenant_id, name, version, is_active, strategy, default_effect, rules, created_at, updated_at, created_by) FROM stdin;
\.


--
-- Data for Name: admissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.admissions (id, patient_id, sector, habitacion, cama, fecha_ingreso, fecha_egreso, protocolo, admision_num, estado, tenant_id) FROM stdin;
048d6cc2-6e30-c619-087a-4fc1aa842766	15a25b2f-f9e2-4fec-ae50-4d7c4cbc812c	\N	\N	\N	2026-01-20 02:11:55	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
9c986454-a45e-c499-1041-28fa94e4a1ab	AINSTEIN_20347	\N	\N	\N	2026-01-22 21:36:25	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
362b60dd-fe08-aba2-14f8-6230225e86bc	AINSTEIN_378121	\N	\N	\N	2026-01-15 03:15:44	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
c2edb263-e372-fd9d-55ff-618f49ead5ee	AINSTEIN_378262	\N	\N	\N	2026-01-15 13:00:44	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
90238d6a-aa01-4063-4c85-cebb8ce2d3e2	AINSTEIN_378413	\N	\N	\N	2026-01-15 14:19:04	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
b692a16b-f72e-d633-2b1e-c64de901d930	AINSTEIN_378471	\N	\N	\N	2026-01-20 23:36:41	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
6136f20d-524b-76cd-f6f5-b584bd6211fe	AINSTEIN_378932	\N	\N	\N	2026-01-15 12:03:22	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
34d39205-71f5-f5a0-752a-f833fe73e870	AINSTEIN_379213	\N	\N	\N	2026-01-16 04:28:41	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
7e8b0105-019e-15e7-0bb9-98bb051b6a26	AINSTEIN_379311	\N	\N	\N	2026-01-20 22:42:51	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
e849f238-d9f2-7efd-eee7-e56a0269b1f9	AINSTEIN_381537	\N	\N	\N	2026-01-17 12:32:28	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
ecc69ffb-3fe0-019a-0313-dda59f90eb85	AINSTEIN_381776	\N	\N	\N	2026-01-16 12:12:08	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
ee87c676-e708-4660-44bc-85d0368f1dd1	AINSTEIN_383433	\N	\N	\N	2026-01-20 01:58:13	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
b1320bc7-445c-fce6-db7e-6d9384810022	AINSTEIN_387454	\N	\N	\N	2026-01-21 13:29:17	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
f0e8137c-120e-dd0b-a533-6d7ccc501869	AINSTEIN_401410	\N	\N	\N	2026-01-16 13:25:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
7d834a39-658b-2abd-30dc-3ac453b6394c	AINSTEIN_402006	\N	\N	\N	2026-01-16 23:43:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
742bc51e-31de-4884-9c3a-de531d2871e3	AINSTEIN_403371	\N	\N	\N	2026-01-20 12:30:28	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
2dfb34c1-818f-7001-b821-c6edac076e43	AINSTEIN_409872	\N	\N	\N	2026-01-21 04:27:50	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
2f3c3812-f9d2-744a-c0e3-c43809b907b4	AINSTEIN_411729	\N	\N	\N	2026-01-20 02:58:59	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
e8f14f3e-e5fe-2a15-78ab-e10bd0860d83	AINSTEIN_415470	\N	\N	\N	2026-01-21 13:26:21	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
5087e736-5d80-5013-b8e2-b7d14f39dc88	AINSTEIN_427997	\N	\N	\N	2026-01-20 19:41:38	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
524871e9-0034-03a6-a2ec-0371f0ecc3ce	AINSTEIN_430173	\N	\N	\N	2026-01-17 14:59:14	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
346a5f3d-9c5c-24a5-e55c-52e2ff939ac6	AINSTEIN_435974	\N	\N	\N	2026-01-17 13:01:16	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
f7836d11-3e81-8ec8-541c-0767f37b368d	AINSTEIN_438721	\N	\N	\N	2026-01-17 15:29:22	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
eb3a3f78-6b18-0386-6b7a-668f6fc3b4a4	AINSTEIN_444893	\N	\N	\N	2026-01-27 02:54:55	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
ec03ec5f-af59-a0b0-78b5-4356942d72f9	AINSTEIN_462059	\N	\N	\N	2026-01-21 13:30:12	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
5a998816-d33e-cfaf-dac1-cf67359a0fa3	AINSTEIN_463778	\N	\N	\N	2026-01-16 17:40:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
52300936-ccc2-6c3f-6768-7df1706d8b74	AINSTEIN_484660	\N	\N	\N	2026-01-21 13:25:12	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
2f7f5529-12e9-b140-e211-790a48f226a0	AINSTEIN_487379	\N	\N	\N	2026-01-21 13:30:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
77991bd8-e01d-a6e8-3d92-75c2fc278f34	AINSTEIN_500339	\N	\N	\N	2026-01-16 23:20:35	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
56e5041e-c7ac-4e4f-9dba-ee39ab41a6a8	AINSTEIN_500599	\N	\N	\N	2026-01-19 14:12:24	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
021912ee-90a9-2b19-6277-5d3820baf056	AINSTEIN_524430	\N	\N	\N	2026-01-19 22:20:04	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
286d7458-e54b-29ae-ca07-9d893a30da59	AINSTEIN_524534	\N	\N	\N	2026-01-19 22:13:03	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
06608a4e-c808-5532-0c7b-f46cde764cf0	AINSTEIN_532721	\N	\N	\N	2026-01-20 13:23:19	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
06bf7973-93e6-d085-ccff-61c970ffaca5	AINSTEIN_533485	\N	\N	\N	2026-01-18 14:38:31	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
eac2cc21-a2be-87b8-16a3-d582f3e3c13c	AINSTEIN_535420	\N	\N	\N	2026-01-23 11:49:34	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
563d7fb9-a6c6-5272-67a1-cb484550398d	AINSTEIN_546749	\N	\N	\N	2026-01-26 14:49:04	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
35e49d2b-1a87-a393-cc7e-6d238cca8944	AINSTEIN_548565	\N	\N	\N	2026-01-19 17:00:23	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
3743dca9-34c2-a060-c257-f1bf0581cd05	AINSTEIN_549183	\N	\N	\N	2026-01-19 00:03:16	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
c2cc71e1-3583-29dc-6299-23db67c4d769	AINSTEIN_554729	\N	\N	\N	2026-01-17 14:23:07	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
f2f9b1f3-717b-6359-017c-ad03de15e5db	AINSTEIN_556336	\N	\N	\N	2026-01-16 12:42:55	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
12788e72-2b71-899c-02f4-7aeef21abb09	AINSTEIN_558635	\N	\N	\N	2026-01-20 20:11:17	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
2979196e-5a44-d4b4-cb12-0cc0c597b0c6	AINSTEIN_559674	\N	\N	\N	2026-01-19 00:41:36	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
d869102e-1b3a-4aae-b723-3846f59987e9	AINSTEIN_559808	\N	\N	\N	2026-01-17 13:33:20	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
43fb5516-f952-ba95-6880-625c4f6425ef	AINSTEIN_559971	\N	\N	\N	2026-01-20 19:08:50	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
38be3ca7-ffa6-56a9-0dc7-b0739d5187da	AINSTEIN_560058	\N	\N	\N	2026-01-20 21:22:43	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
4b10a71b-fea3-cdfd-c942-808cc9da013c	AINSTEIN_10258	\N	\N	\N	2026-01-23 18:03:57	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
f0a12386-18a6-22bf-71a8-484bec417f32	AINSTEIN_383615	\N	\N	\N	2026-01-17 19:49:28	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
9eac9068-ec2b-23e7-d312-77e838c0b541	AINSTEIN_378705	\N	\N	\N	2026-01-21 13:28:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
4a2ca279-3c36-8210-ff43-1d0cd5d4db82	AINSTEIN_380099	\N	\N	\N	2026-01-17 13:54:12	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
ecdf9c27-3f83-fe53-8105-95019ca02b08	AINSTEIN_560065	\N	\N	\N	2026-01-20 21:53:39	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
3d1f8d2c-949e-4e94-af1e-87de18cdc754	AINSTEIN_382761	\N	\N	\N	2026-01-25 01:21:55	\N	\N	39757	epc_generada	\N
74a654b3-c584-4104-87e5-f5693045a668	AINSTEIN_461196	\N	\N	\N	2026-01-14 21:37:24	\N	\N	39555	epc_generada	\N
a1d18d23-9276-1f90-5626-d128595d61b3	AINSTEIN_378574	\N	\N	\N	2026-01-20 15:28:01	\N	\N	\N	epc_generada	00000000-0000-0000-0000-000000000001
cfc540ba-f28b-4f17-9184-bb52795e3d5e	AINSTEIN_417995	\N	\N	\N	2024-12-18 18:55:54	\N	\N	29769	epc_generada	\N
df675dbe-76a1-4c52-b0c1-462e29c8bef2	AINSTEIN_387695	\N	\N	\N	2023-09-12 20:36:40	\N	\N	17641	epc_generada	\N
2a191220-4bbe-428b-97a7-f138817a8b69	AINSTEIN_561672	\N	\N	\N	2026-02-03 09:11:55	\N	\N	39947	epc_generada	\N
210e8bd7-0a30-4238-8910-4a8b0547a16e	AINSTEIN_379457	\N	\N	\N	2026-02-01 14:21:32	\N	\N	39909	epc_generada	\N
746cac60-f7e6-4a77-a5cf-36a0aeae832a	AINSTEIN_532743	\N	\N	\N	2025-02-07 13:03:43	\N	\N	30766	epc_generada	\N
a9b467fc-5851-4559-9938-ff011fea4ea4	AINSTEIN_405680	\N	\N	\N	2026-01-28 15:40:00	\N	\N	39838	epc_generada	\N
94b9316b-1c56-4cb1-b953-2aaf457589e0	AINSTEIN_538874	\N	\N	\N	2026-01-23 15:20:10	\N	\N	39744	epc_generada	\N
e5c1199e-48e7-48cb-922c-1ce6867dd287	AINSTEIN_537951	\N	\N	\N	2026-01-29 12:40:03	\N	\N	39864	internacion	\N
e4290034-4fc9-49d6-b994-d4f78d9942ab	AINSTEIN_430261	\N	\N	\N	2026-01-25 14:09:50	\N	\N	39762	epc_generada	\N
01c46eea-e6a9-4aed-b7cf-33968351eb5d	AINSTEIN_381308	\N	\N	\N	2026-01-25 07:32:19	\N	\N	39759	epc_generada	\N
9e1accce-714e-4eca-b47b-67cab15017e2	AINSTEIN_529170	\N	\N	\N	2026-02-04 12:03:42	\N	\N	39980	epc_generada	\N
cf613da0-a402-4baf-86a1-78d542802c65	AINSTEIN_410471	\N	\N	\N	2026-01-28 12:59:00	\N	\N	39832	epc_generada	\N
a9b06d91-376f-4f7d-b70e-9a21a43df9f1	AINSTEIN_409970	\N	\N	\N	2022-01-10 23:28:08	\N	\N	2843	epc_generada	\N
de8c6b70-d854-45ea-b479-d567a37b5d58	AINSTEIN_389468	\N	\N	\N	2024-01-24 11:10:25	\N	\N	20950	epc_generada	\N
158183f4-d86d-4f69-bc14-385154c007c3	AINSTEIN_425540	\N	\N	\N	2026-01-30 17:59:01	\N	\N	39893	internacion	\N
47090125-e702-4a88-a5bd-b588d44a1436	AINSTEIN_560894	\N	\N	\N	2026-01-21 21:21:41	\N	\N	39705	internacion	\N
29a153a6-2da2-42da-8d00-f0a5fa7382e6	AINSTEIN_461196	\N	\N	\N	2026-01-14 21:37:24	\N	\N	39555	epc_generada	\N
9c99eb1b-1e73-410c-844b-896014c6baf4	AINSTEIN_418384	\N	\N	\N	2026-01-25 22:00:22	\N	\N	39765	internacion	\N
b9c1ee53-974b-408a-bc19-ba22707cbdc0	AINSTEIN_546475	\N	\N	\N	2026-01-19 10:40:22	\N	\N	39646	epc_generada	\N
bdb5aa71-919b-4af6-ae00-2d26a54f0f6f	AINSTEIN_464085	\N	\N	\N	2023-08-17 17:34:34	\N	\N	16974	internacion	\N
48f8a200-2ffc-4287-b5b2-8e335d7003eb	AINSTEIN_544941	\N	\N	\N	2026-01-29 15:53:32	\N	\N	39872	epc_generada	\N
9dafad39-d769-4103-9b42-61601fcf1637	AINSTEIN_477619	\N	\N	\N	2023-12-05 09:20:07	\N	\N	19867	epc_generada	\N
40913156-9c52-4346-ae48-1df0335cab7b	AINSTEIN_380216	\N	\N	\N	2026-02-14 22:04:29	\N	\N	40251	epc_generada	\N
9f0d2d92-63d5-4538-97b8-703b04779827	AINSTEIN_434312	\N	\N	\N	2022-11-11 18:45:46	\N	\N	10262	epc_generada	\N
d7dc2cb9-06b8-4ba8-a8c0-cee2955fde13	AINSTEIN_408552	\N	\N	\N	2023-02-24 22:05:07	\N	\N	12522	epc_generada	\N
5e3859aa-e02b-4320-a066-5635907880f7	AINSTEIN_400817	\N	\N	\N	2023-04-25 23:54:44	\N	\N	13969	epc_generada	\N
a7782b24-6a59-40c9-8fe0-a4eddda88116	AINSTEIN_382647	\N	\N	\N	2026-01-13 16:45:37	\N	\N	39518	epc_generada	\N
f8eb3be9-c95c-482d-8f34-017967fd3b20	AINSTEIN_401694	\N	\N	\N	2021-11-18 07:13:41	\N	\N	1767	epc_generada	\N
583a006d-fa98-427f-94c3-7a2d0e02ee3c	AINSTEIN_464085	\N	\N	\N	2023-08-17 17:34:34	\N	\N	16974	epc_generada	\N
9f6aaffa-53a0-43e7-978f-6308ee1c78dd	AINSTEIN_405680	\N	\N	\N	2026-01-28 15:40:00	\N	\N	39838	internacion	\N
79e997c6-3a11-44af-817d-36c437dac6b6	AINSTEIN_506015	\N	\N	\N	2024-06-04 01:31:09	\N	\N	24195	epc_generada	\N
71a6ab84-6b4c-4686-864d-7622126e131d	AINSTEIN_407451	\N	\N	\N	2023-03-31 15:47:32	\N	\N	13353	epc_generada	\N
8d051616-a5f8-4dfd-b519-646b185119b3	AINSTEIN_506015	\N	\N	\N	2024-06-04 01:31:09	\N	\N	24195	internacion	\N
2928c7ad-2c0e-43d1-887a-bfcc13434b05	AINSTEIN_506015	\N	\N	\N	2025-06-04 10:13:48	\N	\N	33599	internacion	\N
92b4bc96-8288-4d0a-bbaa-5be08c2dd89b	AINSTEIN_506015	\N	\N	\N	2025-06-04 10:13:48	\N	\N	33599	internacion	\N
471004a3-069b-43e1-ae4e-61f71412f81e	AINSTEIN_506015	\N	\N	\N	2025-03-31 10:55:39	\N	\N	31949	internacion	\N
2c617cb0-5955-4e90-bf59-6d0280f991f7	AINSTEIN_506015	\N	\N	\N	2024-06-04 01:31:09	\N	\N	24195	internacion	\N
0f81690e-17ea-45b1-9c41-a02436416372	AINSTEIN_464085	\N	\N	\N	2023-08-17 17:34:34	\N	\N	16974	internacion	\N
df97bbff-970b-4c09-8c13-35f4aa3f49d1	AINSTEIN_408552	\N	\N	\N	2023-02-24 22:05:07	\N	\N	12522	internacion	\N
2662eb47-bbc6-444d-89f0-c70f1a56b0d4	AINSTEIN_407451	\N	\N	\N	2023-03-31 15:47:32	\N	\N	13353	internacion	\N
52b869b5-5628-4dc8-9c85-8c71fccd076a	AINSTEIN_387695	\N	\N	\N	2023-09-12 20:36:40	\N	\N	17641	internacion	\N
243a0c83-c873-43f3-818c-715d8967ea8a	AINSTEIN_529170	\N	\N	\N	2026-02-04 12:03:42	\N	\N	39980	internacion	\N
67f9f5c3-df87-4ede-b7e4-0d77760d84d8	AINSTEIN_535420	\N	\N	\N	2025-03-06 20:42:19	\N	\N	31375	internacion	\N
c62a7037-06f8-499c-88f3-4f81523c6d18	AINSTEIN_532743	\N	\N	\N	2025-02-07 13:03:43	\N	\N	30766	internacion	\N
56378783-05d0-4613-85b6-77d2d7a853e0	AINSTEIN_532721	\N	\N	\N	2025-04-17 07:07:13	\N	\N	32373	internacion	\N
98443a57-e95a-4ebd-afa5-875d54aeb7dc	AINSTEIN_532721	\N	\N	\N	2025-04-17 07:07:13	\N	\N	32373	internacion	\N
7217a4a6-2414-4658-a9b5-612eb65b47d3	AINSTEIN_20580	\N	\N	\N	2026-02-12 13:18:39	\N	\N	40203	epc_generada	\N
21099fe4-42a6-49d5-920e-848298472336	AINSTEIN_385518	\N	\N	\N	2026-02-04 19:23:14	\N	\N	39996	epc_generada	\N
33697541-5ccc-4002-af24-92c16667c895	AINSTEIN_385518	\N	\N	\N	2026-02-04 19:23:14	\N	\N	39996	internacion	\N
7debeca2-987f-45d0-94ef-6c3ae3ed0aac	AINSTEIN_406793	\N	\N	\N	2022-03-13 13:42:48	\N	\N	4031	epc_generada	\N
46552f3e-0572-4cd6-a34c-8f2ed2b88308	AINSTEIN_417995	\N	\N	\N	2024-12-18 18:55:54	\N	\N	29769	internacion	\N
defa81f2-07a6-40a9-bcb1-0bcb24f09a87	AINSTEIN_409970	\N	\N	\N	2022-01-10 23:28:08	\N	\N	2843	internacion	\N
3c6b37da-d277-47a3-861f-5e460fe0bacf	AINSTEIN_406793	\N	\N	\N	2022-03-13 13:42:48	\N	\N	4031	internacion	\N
1de87894-7bc5-47fc-8658-dbae35566a8f	AINSTEIN_406793	\N	\N	\N	2022-03-13 13:42:48	\N	\N	4031	internacion	\N
82e349fb-4ec9-4f26-b893-ef2dfce4286e	AINSTEIN_562571	\N	\N	\N	2026-02-15 00:58:25	\N	\N	40252	epc_generada	\N
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
a352f64b3cff
\.


--
-- Data for Name: branding; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.branding (id, hospital_nombre, logo_url, header_linea1, header_linea2, footer_linea1, footer_linea2, updated_at, tenant_id) FROM stdin;
1	Clínica Markey	\N	\N	\N	\N	\N	2026-01-30 22:07:35.234042	00000000-0000-0000-0000-000000000001
\.


--
-- Data for Name: epc; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.epc (id, patient_id, admission_id, estado, version_actual_oid, titulo, diagnostico_principal_cie10, fecha_emision, medico_responsable, firmado_por_medico, created_by, created_at, updated_at, motivo_internacion, evolucion, procedimientos, interconsultas, medicacion, indicaciones_alta, recomendaciones, last_edited_by, last_edited_at, has_manual_changes, regenerated_count, tenant_id) FROM stdin;
\.


--
-- Data for Name: epc_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.epc_events (id, epc_id, at, by, action) FROM stdin;
14	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-11-21 21:18:18	admin	EPC generada por IA
18	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-11-21 21:30:41	admin	EPC generada por IA
20	31cac675-fdb6-419e-b2d9-19fc1998dc80	2025-11-22 00:23:32	pdimitroff	EPC creada
21	31cac675-fdb6-419e-b2d9-19fc1998dc80	2025-11-22 00:23:44	pdimitroff	EPC generada por IA
24	1b2a1911-f966-4f40-b15e-73be43c05400	2025-11-24 23:05:44	admin	EPC creada
25	1b2a1911-f966-4f40-b15e-73be43c05400	2025-11-24 23:05:56	admin	EPC generada por IA
26	9fece7da-ec46-4947-9183-9e2a678d6fbc	2025-11-25 13:23:04	admin	EPC creada
27	9fece7da-ec46-4947-9183-9e2a678d6fbc	2025-11-25 13:23:12	admin	EPC generada por IA
30	30bde057-1e6b-4021-923b-709782d82e98	2025-11-28 01:09:48	admin	EPC creada
31	30bde057-1e6b-4021-923b-709782d82e98	2025-11-28 01:09:56	admin	EPC generada por IA
33	376daf08-c266-47b8-a8e5-28cbdb8fd7dc	2025-12-04 17:15:04	admin	EPC creada
34	376daf08-c266-47b8-a8e5-28cbdb8fd7dc	2025-12-04 17:15:13	admin	EPC generada por IA
35	622e62cf-59c7-434a-8250-1b6b2fe3a58a	2025-12-09 13:30:48	gustavop	EPC creada
36	622e62cf-59c7-434a-8250-1b6b2fe3a58a	2025-12-09 13:31:02	gustavop	EPC generada por IA
38	d2b60870-5fc9-46c0-98f2-09cccf950330	2025-12-10 14:13:01	admin	EPC creada
39	d2b60870-5fc9-46c0-98f2-09cccf950330	2025-12-10 14:13:13	admin	EPC generada por IA
40	8d1c901e-00dc-4f5d-a033-2df155df28fc	2025-12-10 14:16:36	admin	EPC creada
41	8d1c901e-00dc-4f5d-a033-2df155df28fc	2025-12-10 14:16:45	admin	EPC generada por IA
45	d2b60870-5fc9-46c0-98f2-09cccf950330	2025-12-16 18:38:14	admin	EPC generada por IA
46	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-12-16 18:40:18	admin	EPC generada por IA
47	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-12-16 19:05:09	admin	EPC generada por IA
48	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-12-16 19:08:27	admin	EPC generada por IA
49	ca01980e-2743-4daa-9088-65e5a6e571e7	2025-12-16 19:13:27	admin	EPC generada por IA
50	376daf08-c266-47b8-a8e5-28cbdb8fd7dc	2025-12-16 19:14:58	admin	EPC generada por IA
51	5e8fd913-e3d6-4f34-af26-99280d57a467	2025-12-16 19:16:18	admin	EPC creada
52	5e8fd913-e3d6-4f34-af26-99280d57a467	2025-12-16 19:16:32	admin	EPC generada por IA
54	5e8fd913-e3d6-4f34-af26-99280d57a467	2025-12-16 19:28:33	admin	EPC generada por IA
55	5e8fd913-e3d6-4f34-af26-99280d57a467	2025-12-16 19:40:44	admin	EPC generada por IA
56	30bde057-1e6b-4021-923b-709782d82e98	2025-12-16 20:04:35	admin	EPC generada por IA
57	7af9b126-c70b-46e0-9494-1807e7e23333	2025-12-17 19:05:46	admin	EPC creada
58	7af9b126-c70b-46e0-9494-1807e7e23333	2025-12-17 19:05:54	admin	EPC generada por IA
59	f91aab34-c5eb-4fe9-85bc-0f9c69935e27	2025-12-17 19:08:00	admin	EPC creada
60	f91aab34-c5eb-4fe9-85bc-0f9c69935e27	2025-12-17 19:08:06	admin	EPC generada por IA
61	c01c2cbc-a526-48e2-abc6-e3f2c7e2d3ef	2025-12-22 10:39:01	Nelias	EPC creada
62	c01c2cbc-a526-48e2-abc6-e3f2c7e2d3ef	2025-12-22 10:39:09	Nelias	EPC generada por IA
64	f79cde6d-5d82-4de1-8fca-d2921f5a939f	2025-12-22 10:46:35	Mroverano	EPC creada
65	f79cde6d-5d82-4de1-8fca-d2921f5a939f	2025-12-22 10:46:42	Mroverano	EPC generada por IA
66	65a04b1b-b4b3-4036-b4b5-74e67e7b7c46	2025-12-22 12:22:18	Nelias	EPC creada
67	65a04b1b-b4b3-4036-b4b5-74e67e7b7c46	2025-12-22 12:22:26	Nelias	EPC generada por IA
68	b451b366-5422-4800-89b8-c59b5b1200db	2025-12-22 23:48:51	admin	EPC creada
69	b451b366-5422-4800-89b8-c59b5b1200db	2025-12-22 23:48:58	admin	EPC generada por IA
70	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-24 19:10:06	admin	EPC creada
71	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-24 19:10:10	admin	EPC generada por IA
72	1479579a-e56b-4cef-9d2c-7e125cd7a4c4	2025-12-26 04:07:59	admin	EPC creada
73	1479579a-e56b-4cef-9d2c-7e125cd7a4c4	2025-12-26 04:08:03	admin	EPC generada por IA
74	b6cb332c-4ff7-4023-8acb-9031a26ae195	2025-12-26 12:55:56	admin	EPC creada
75	b6cb332c-4ff7-4023-8acb-9031a26ae195	2025-12-26 12:56:00	admin	EPC generada por IA
77	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-26 13:29:57	admin	EPC generada por IA
78	c01c2cbc-a526-48e2-abc6-e3f2c7e2d3ef	2025-12-26 14:19:35	admin	EPC generada por IA
79	9f31ca09-32e5-4f0e-a1d3-2c3f233b4e64	2025-12-26 15:40:29	MEConsejero	EPC creada
80	9f31ca09-32e5-4f0e-a1d3-2c3f233b4e64	2025-12-26 15:40:36	MEConsejero	EPC generada por IA
81	d35324d7-b23c-457c-896f-3da9c3611448	2025-12-26 16:34:33	admin	EPC creada
82	d35324d7-b23c-457c-896f-3da9c3611448	2025-12-26 16:34:36	admin	EPC generada por IA
83	dc8555f2-8484-4f04-82d7-9e125d01f053	2025-12-26 17:00:36	admin	EPC creada
84	dc8555f2-8484-4f04-82d7-9e125d01f053	2025-12-26 17:00:40	admin	EPC generada por IA
85	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-26 17:23:58	admin	EPC generada por IA
86	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-26 18:06:15	admin	EPC generada por IA
87	55e18d30-e317-41f4-b07e-084d87b1a137	2025-12-26 18:07:36	admin	EPC generada por IA
88	3dfeb059-0df5-4c2f-922c-38c5f173b6d3	2025-12-26 18:14:08	admin	EPC creada
89	3dfeb059-0df5-4c2f-922c-38c5f173b6d3	2025-12-26 18:14:12	admin	EPC generada por IA
90	4c799ae2-bcc9-41c0-9fed-f71f232f2154	2025-12-26 18:17:56	admin	EPC creada
91	4c799ae2-bcc9-41c0-9fed-f71f232f2154	2025-12-26 18:18:00	admin	EPC generada por IA
92	50f9bc39-d1a8-463d-9218-5d19f6863262	2025-12-26 19:34:22	admin	EPC creada
93	d4f5a41f-1f22-4526-ac9d-e4d0e98a125c	2025-12-26 21:48:19	Mroverano	EPC creada
94	d4f5a41f-1f22-4526-ac9d-e4d0e98a125c	2025-12-26 21:48:26	Mroverano	EPC generada por IA
95	2641b88b-d3d3-4c2b-bac8-837ef43536c6	2025-12-29 15:51:17	admin	EPC creada
96	92bc727d-af9c-4607-b7de-9545f75d7487	2025-12-30 15:14:27	admin	EPC creada
97	92bc727d-af9c-4607-b7de-9545f75d7487	2025-12-30 15:14:32	admin	EPC generada por IA
99	b787d4c2-d5ff-4002-800b-7d7d8477b823	2026-01-02 20:48:55	admin	EPC creada
100	b787d4c2-d5ff-4002-800b-7d7d8477b823	2026-01-02 20:49:01	admin	EPC generada por IA
101	9b70ed3c-bfa2-4174-bb6d-b2ff69082aec	2026-01-11 01:50:31	Hbritto	EPC creada
102	9b70ed3c-bfa2-4174-bb6d-b2ff69082aec	2026-01-11 01:50:34	Hbritto	EPC generada por IA
103	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-01-12 15:19:32	admin	EPC creada
104	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-01-12 15:19:41	admin	EPC generada por IA
105	b0fc8c2c-cfdb-44bf-857c-10041a14af2f	2026-01-12 15:23:47	admin	EPC creada
106	b0fc8c2c-cfdb-44bf-857c-10041a14af2f	2026-01-12 15:23:52	admin	EPC generada por IA
109	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-01-12 17:20:47	admin	EPC generada por IA
110	c29320b6-27ed-4d28-92e3-9da9b087cbaf	2026-01-12 18:26:24	admin	EPC creada
111	c29320b6-27ed-4d28-92e3-9da9b087cbaf	2026-01-12 18:26:29	admin	EPC generada por IA
112	1c7b3a53-a77a-492e-9b08-c7649c3f53ed	2026-01-12 18:42:45	admin	EPC creada
113	1c7b3a53-a77a-492e-9b08-c7649c3f53ed	2026-01-12 18:42:51	admin	EPC generada por IA
115	bfc8da7a-ae4f-4903-9d16-28b0802c8e2e	2026-01-12 18:52:37	admin	EPC creada
116	bfc8da7a-ae4f-4903-9d16-28b0802c8e2e	2026-01-12 18:52:43	admin	EPC generada por IA
117	b0fc8c2c-cfdb-44bf-857c-10041a14af2f	2026-01-12 19:06:01	admin	EPC generada por IA
118	b0fc8c2c-cfdb-44bf-857c-10041a14af2f	2026-01-12 19:06:15	admin	EPC generada por IA
119	7dcbbc1c-15ac-4cd0-ba16-29ef05038465	2026-01-13 05:13:56	admin	EPC creada
120	7dcbbc1c-15ac-4cd0-ba16-29ef05038465	2026-01-13 05:14:02	admin	EPC generada por IA
122	5df0c642-0ed3-4e62-8ebf-d940cb82d3e6	2026-01-14 15:21:41	admin	EPC creada
123	5df0c642-0ed3-4e62-8ebf-d940cb82d3e6	2026-01-14 15:21:47	admin	EPC generada por IA
124	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-01-14 15:24:45	admin	EPC generada por IA
125	fa1ef20e-b566-467f-b467-db715d75b4f5	2026-01-14 19:17:53	admin	EPC creada
126	fa1ef20e-b566-467f-b467-db715d75b4f5	2026-01-14 19:18:00	admin	EPC generada por IA
127	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-15 01:14:27	admin	EPC creada
128	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-15 01:14:33	admin	EPC generada por IA
130	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-15 01:39:36	admin	EPC generada por IA
132	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-15 02:05:18	admin	EPC generada por IA
134	c0d895ba-d985-4fbc-8c35-3aecd6af2707	2026-01-15 03:15:49	aaltamirano	EPC creada
135	c0d895ba-d985-4fbc-8c35-3aecd6af2707	2026-01-15 03:15:53	aaltamirano	EPC generada por IA
137	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-15 12:06:10	aaltamirano	EPC generada por IA
138	490914d9-dc51-4dfb-8195-b7ef720c9b90	2026-01-15 13:35:25	Nelias	EPC creada
139	490914d9-dc51-4dfb-8195-b7ef720c9b90	2026-01-15 13:35:31	Nelias	EPC generada por IA
141	7f15233b-c1c1-4d91-8ecf-ea06e421f6e5	2026-01-15 14:31:43	Nelias	EPC creada
142	7f15233b-c1c1-4d91-8ecf-ea06e421f6e5	2026-01-15 14:31:51	Nelias	EPC generada por IA
144	2bec567e-6e3d-4f37-bebe-7b92d726a443	2026-01-16 04:28:55	Nelias	EPC creada
145	2bec567e-6e3d-4f37-bebe-7b92d726a443	2026-01-16 04:29:01	Nelias	EPC generada por IA
148	f082cfda-9ec3-4748-8f3d-9142d5b28202	2026-01-16 12:25:56	aaltamirano	EPC creada
149	f082cfda-9ec3-4748-8f3d-9142d5b28202	2026-01-16 12:26:05	aaltamirano	EPC generada por IA
151	0ddbb1ce-7db2-4131-91e7-5562d16a0ba4	2026-01-16 12:54:47	aaltamirano	EPC creada
152	0ddbb1ce-7db2-4131-91e7-5562d16a0ba4	2026-01-16 12:54:55	aaltamirano	EPC generada por IA
154	d53517ca-9497-4ad9-938b-c1e466478f91	2026-01-16 13:22:14	zeron	EPC creada
155	d53517ca-9497-4ad9-938b-c1e466478f91	2026-01-16 13:22:16	zeron	EPC generada por IA
156	6ecfccba-817d-4974-b607-11b502e11a33	2026-01-16 13:44:31	aaltamirano	EPC creada
157	6ecfccba-817d-4974-b607-11b502e11a33	2026-01-16 13:44:41	aaltamirano	EPC generada por IA
158	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 13:49:32	zeron	EPC creada
159	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 13:49:37	zeron	EPC generada por IA
161	91301c1e-fd46-435f-b841-c7ab2a28629e	2026-01-16 17:40:24	Nelias	EPC creada
162	91301c1e-fd46-435f-b841-c7ab2a28629e	2026-01-16 17:40:31	Nelias	EPC generada por IA
164	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 19:18:11	admin	EPC generada por IA
165	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 19:21:02	admin	EPC generada por IA
166	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 19:29:31	admin	EPC generada por IA
167	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 23:20:23	admin	EPC generada por IA
168	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 23:29:10	admin	EPC generada por IA
169	241dc94d-a812-4304-8781-59957dbe2d4b	2026-01-16 23:34:18	aaltamirano	EPC creada
170	241dc94d-a812-4304-8781-59957dbe2d4b	2026-01-16 23:34:25	aaltamirano	EPC generada por IA
171	da3bf7d9-02f8-4f42-b20a-329b21af2c39	2026-01-16 23:41:56	admin	EPC generada por IA
172	17b87962-4619-492b-bef9-de707394d76d	2026-01-16 23:44:13	admin	EPC creada
173	17b87962-4619-492b-bef9-de707394d76d	2026-01-16 23:44:18	admin	EPC generada por IA
176	241dc94d-a812-4304-8781-59957dbe2d4b	2026-01-16 23:55:51	aaltamirano	EPC generada por IA
177	ccfbd1d6-16a0-4f59-aae8-fca4bdbcafff	2026-01-17 06:25:55	secimino	EPC creada
178	ccfbd1d6-16a0-4f59-aae8-fca4bdbcafff	2026-01-17 06:25:59	secimino	EPC generada por IA
179	f5427c82-7690-4e64-9cce-4a409a40767d	2026-01-17 06:27:03	secimino	EPC creada
180	f5427c82-7690-4e64-9cce-4a409a40767d	2026-01-17 06:27:17	secimino	EPC generada por IA
181	0097c855-b8b2-4901-a52e-3b7cf59ef1cc	2026-01-17 06:27:52	secimino	EPC creada
182	0097c855-b8b2-4901-a52e-3b7cf59ef1cc	2026-01-17 06:28:00	secimino	EPC generada por IA
183	7daeedf5-8ea1-4534-86c0-9bb5c2f98dc7	2026-01-17 06:30:24	secimino	EPC creada
184	7daeedf5-8ea1-4534-86c0-9bb5c2f98dc7	2026-01-17 06:30:30	secimino	EPC generada por IA
185	aecae82c-00f1-4349-a9ad-54fefae6d90b	2026-01-17 06:31:11	secimino	EPC creada
186	aecae82c-00f1-4349-a9ad-54fefae6d90b	2026-01-17 06:31:17	secimino	EPC generada por IA
187	2badd0dd-5aa5-45d0-8eed-ea9c7f1b6f51	2026-01-17 06:32:01	secimino	EPC creada
188	2badd0dd-5aa5-45d0-8eed-ea9c7f1b6f51	2026-01-17 06:32:09	secimino	EPC generada por IA
189	2e3a996c-25cb-49c5-896c-91996e1e2b32	2026-01-17 06:33:56	secimino	EPC creada
190	2e3a996c-25cb-49c5-896c-91996e1e2b32	2026-01-17 06:34:02	secimino	EPC generada por IA
191	e24abaf1-edd1-48c0-8cfc-43e08de53f04	2026-01-17 06:34:22	secimino	EPC creada
192	e24abaf1-edd1-48c0-8cfc-43e08de53f04	2026-01-17 06:34:26	secimino	EPC generada por IA
194	ec147174-72ff-472e-9e52-63c125f954f8	2026-01-17 12:42:02	aaltamirano	EPC creada
195	ec147174-72ff-472e-9e52-63c125f954f8	2026-01-17 12:42:08	aaltamirano	EPC generada por IA
197	6083ac77-8751-4bbe-a6df-921f5c4ff9b1	2026-01-17 13:11:53	aaltamirano	EPC creada
198	6083ac77-8751-4bbe-a6df-921f5c4ff9b1	2026-01-17 13:12:08	aaltamirano	EPC generada por IA
199	2e3a996c-25cb-49c5-896c-91996e1e2b32	2026-01-17 13:33:42	Mroverano	EPC generada por IA
201	58d76a91-f0ca-4f1c-bf04-aa4d3df7ea3b	2026-01-17 14:01:17	secimino	EPC creada
202	58d76a91-f0ca-4f1c-bf04-aa4d3df7ea3b	2026-01-17 14:01:23	secimino	EPC generada por IA
203	fa1ef20e-b566-467f-b467-db715d75b4f5	2026-01-17 14:13:43	Mroverano	EPC generada por IA
205	9d8bd79a-6410-4508-b5a1-c8373a27a1d7	2026-01-17 14:39:48	Mroverano	EPC creada
206	9d8bd79a-6410-4508-b5a1-c8373a27a1d7	2026-01-17 14:39:57	Mroverano	EPC generada por IA
208	a63d9fc9-1ba5-47da-9851-7c74d0e17f81	2026-01-17 15:13:31	Mroverano	EPC creada
209	a63d9fc9-1ba5-47da-9851-7c74d0e17f81	2026-01-17 15:13:39	Mroverano	EPC generada por IA
211	d7dd52fc-4b12-4080-b11e-f73d7811421a	2026-01-17 15:42:20	Mroverano	EPC creada
212	d7dd52fc-4b12-4080-b11e-f73d7811421a	2026-01-17 15:42:26	Mroverano	EPC generada por IA
214	38ba5741-03f4-4257-8062-87714bcc8c06	2026-01-18 07:14:29	secimino	EPC creada
215	38ba5741-03f4-4257-8062-87714bcc8c06	2026-01-18 07:14:33	secimino	EPC generada por IA
216	0cee721e-0842-4204-9823-99ff2a9a92f2	2026-01-18 14:41:13	secimino	EPC creada
217	0cee721e-0842-4204-9823-99ff2a9a92f2	2026-01-18 14:41:19	secimino	EPC generada por IA
219	b2cec9ee-a608-4b4f-af97-874a69fda614	2026-01-18 17:15:56	pdimitroff	EPC generada por IA
220	b148b60f-9e9b-400b-9578-1feac9cebb0b	2026-01-19 00:04:18	aaltamirano	EPC creada
221	b148b60f-9e9b-400b-9578-1feac9cebb0b	2026-01-19 00:04:24	aaltamirano	EPC generada por IA
225	8886465d-ff2d-4c11-875e-6a9e45ccb1ba	2026-01-19 00:50:26	aaltamirano	EPC creada
226	8886465d-ff2d-4c11-875e-6a9e45ccb1ba	2026-01-19 00:50:33	aaltamirano	EPC generada por IA
228	c25d7096-9be3-4e22-b75b-aec7fdcfa954	2026-01-19 14:12:47	Nelias	EPC creada
229	c25d7096-9be3-4e22-b75b-aec7fdcfa954	2026-01-19 14:12:53	Nelias	EPC generada por IA
231	60e50648-bffe-4621-bdd0-236f1ad87915	2026-01-19 15:26:00	Nelias	EPC creada
232	60e50648-bffe-4621-bdd0-236f1ad87915	2026-01-19 15:26:06	Nelias	EPC generada por IA
233	bd9c4d1b-6b2d-47a6-8fda-8eec09354b80	2026-01-19 17:00:36	Nelias	EPC creada
234	bd9c4d1b-6b2d-47a6-8fda-8eec09354b80	2026-01-19 17:00:41	Nelias	EPC generada por IA
235	a08a2ccd-5275-4a5b-81c1-8b6543ffad24	2026-01-19 22:18:19	secimino	EPC creada
236	a08a2ccd-5275-4a5b-81c1-8b6543ffad24	2026-01-19 22:18:30	secimino	EPC generada por IA
237	b02f9972-8621-4792-88be-513120c042e6	2026-01-19 22:48:23	aaltamirano	EPC creada
238	b02f9972-8621-4792-88be-513120c042e6	2026-01-19 22:48:31	aaltamirano	EPC generada por IA
241	4f67232d-6354-45e9-aa04-d56038ec5069	2026-01-20 01:58:32	Nelias	EPC creada
242	4f67232d-6354-45e9-aa04-d56038ec5069	2026-01-20 01:58:37	Nelias	EPC generada por IA
243	ed929a81-1213-40b6-ac1c-fa5467f3a69a	2026-01-20 02:12:58	Nelias	EPC creada
244	ed929a81-1213-40b6-ac1c-fa5467f3a69a	2026-01-20 02:13:03	Nelias	EPC generada por IA
247	1e198649-b447-4af2-92a5-9eab074ef24a	2026-01-20 02:59:33	Nelias	EPC creada
248	1e198649-b447-4af2-92a5-9eab074ef24a	2026-01-20 02:59:44	Nelias	EPC generada por IA
250	baf52ccd-1365-490b-9686-3bd75faed797	2026-01-20 12:30:42	Nelias	EPC creada
251	baf52ccd-1365-490b-9686-3bd75faed797	2026-01-20 12:30:50	Nelias	EPC generada por IA
258	048000ec-a84c-412f-84ce-5582681be01a	2026-01-20 15:28:28	Nelias	EPC creada
259	048000ec-a84c-412f-84ce-5582681be01a	2026-01-20 15:28:35	Nelias	EPC generada por IA
263	0097c855-b8b2-4901-a52e-3b7cf59ef1cc	2026-01-20 18:36:53	aaltamirano	EPC generada por IA
264	c3abf788-db15-4dfb-ae53-4523796252fc	2026-01-20 19:40:17	MEConsejero	EPC creada
265	c3abf788-db15-4dfb-ae53-4523796252fc	2026-01-20 19:40:23	MEConsejero	EPC generada por IA
266	012d3486-fd9d-40e4-9165-08009fb71421	2026-01-20 19:43:13	secimino	EPC creada
267	012d3486-fd9d-40e4-9165-08009fb71421	2026-01-20 19:43:18	secimino	EPC generada por IA
268	5dd36a6d-92d7-4164-9a96-18d87d4673e6	2026-01-20 21:14:01	MEConsejero	EPC creada
269	5dd36a6d-92d7-4164-9a96-18d87d4673e6	2026-01-20 21:14:05	MEConsejero	EPC generada por IA
270	fcb83837-c529-4b7e-9be2-4fae64b1bf55	2026-01-20 21:45:18	MEConsejero	EPC creada
271	fcb83837-c529-4b7e-9be2-4fae64b1bf55	2026-01-20 21:45:41	MEConsejero	EPC generada por IA
272	8715b14e-b914-48fa-9f2a-2407c0414a80	2026-01-20 22:24:52	MEConsejero	EPC creada
273	8715b14e-b914-48fa-9f2a-2407c0414a80	2026-01-20 22:24:58	MEConsejero	EPC generada por IA
274	122b56f6-2e75-43a4-a31b-d5db4ddfdcbc	2026-01-20 22:44:00	secimino	EPC creada
275	122b56f6-2e75-43a4-a31b-d5db4ddfdcbc	2026-01-20 22:44:03	secimino	EPC generada por IA
276	b9244a46-5621-49fd-a5fc-c8ca19bcdc70	2026-01-21 04:26:22	secimino	EPC creada
277	b9244a46-5621-49fd-a5fc-c8ca19bcdc70	2026-01-21 04:26:28	secimino	EPC generada por IA
278	85402c5f-61a1-42b8-b43e-7c689ce83e60	2026-01-21 04:27:58	secimino	EPC creada
279	85402c5f-61a1-42b8-b43e-7c689ce83e60	2026-01-21 04:28:13	secimino	EPC generada por IA
280	76513b82-7183-4ca5-93c2-16244e9c6a5d	2026-01-21 13:30:43	secimino	EPC creada
281	76513b82-7183-4ca5-93c2-16244e9c6a5d	2026-01-21 13:30:45	secimino	EPC generada por IA
282	abb5bffd-2404-40c3-9570-56a00bf7ee4e	2026-01-21 13:32:30	secimino	EPC creada
283	abb5bffd-2404-40c3-9570-56a00bf7ee4e	2026-01-21 13:32:39	secimino	EPC generada por IA
284	11bd5eaf-67b4-48f6-b263-e9c07c289b13	2026-01-21 13:34:03	secimino	EPC creada
285	11bd5eaf-67b4-48f6-b263-e9c07c289b13	2026-01-21 13:34:14	secimino	EPC generada por IA
286	dbd660b0-e9ac-4731-8bb0-f489d1c45e35	2026-01-21 13:36:52	secimino	EPC creada
287	dbd660b0-e9ac-4731-8bb0-f489d1c45e35	2026-01-21 13:37:03	secimino	EPC generada por IA
288	da7e084b-4619-4dde-830d-0f33dc6879b9	2026-01-21 13:38:21	secimino	EPC creada
289	da7e084b-4619-4dde-830d-0f33dc6879b9	2026-01-21 13:38:35	secimino	EPC generada por IA
290	eff15649-380b-4f86-87fa-ef7e9e5e139d	2026-01-21 13:39:27	secimino	EPC creada
291	eff15649-380b-4f86-87fa-ef7e9e5e139d	2026-01-21 13:39:51	secimino	EPC generada por IA
292	84936551-6be1-41bf-ad4a-bd1c3a8c4d8a	2026-01-22 21:39:47	secimino	EPC creada
293	84936551-6be1-41bf-ad4a-bd1c3a8c4d8a	2026-01-22 21:39:58	secimino	EPC generada por IA
294	04309513-85f1-4240-8b75-b38b73924486	2026-01-23 12:17:10	aaltamirano	EPC creada
295	04309513-85f1-4240-8b75-b38b73924486	2026-01-23 12:17:26	aaltamirano	EPC generada por IA
296	04309513-85f1-4240-8b75-b38b73924486	2026-01-23 12:18:20	aaltamirano	EPC generada por IA
297	86fe8b05-d66e-41e1-b520-ba4b1e230792	2026-01-23 18:04:20	secimino	EPC creada
298	86fe8b05-d66e-41e1-b520-ba4b1e230792	2026-01-23 18:04:27	secimino	EPC generada por IA
299	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-01-23 20:53:09	secimino	EPC generada por IA
302	5c55cc6c-64f4-4dce-8077-4aa22b893dd0	2026-01-26 14:49:28	Nelias	EPC creada
303	5c55cc6c-64f4-4dce-8077-4aa22b893dd0	2026-01-26 14:49:42	Nelias	EPC generada por IA
304	5c55cc6c-64f4-4dce-8077-4aa22b893dd0	2026-01-26 22:26:12	secimino	EPC generada por IA
306	5fec4459-4aed-41db-8244-b81d34d6b334	2026-01-27 02:55:18	Nelias	EPC creada
307	5fec4459-4aed-41db-8244-b81d34d6b334	2026-01-27 02:55:26	Nelias	EPC generada por IA
1	048000ec-a84c-412f-84ce-5582681be01a	2026-01-30 22:17:09.234167	admin	EPC generada por IA
2	0d58c310-a511-4a73-aa2c-9688230acdca	2026-02-04 17:06:16.741067	secimino	EPC creada
3	0d58c310-a511-4a73-aa2c-9688230acdca	2026-02-04 17:06:20.261904	secimino	EPC generada por IA
4	98d35de1-43ab-4fa2-97ad-807629682620	2026-02-04 17:23:20.129417	secimino	EPC creada
5	98d35de1-43ab-4fa2-97ad-807629682620	2026-02-04 17:23:23.351484	secimino	EPC generada por IA
6	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:17:00.855471	admin	EPC generada por IA
7	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:18:42.72217	admin	EPC generada por IA
8	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:23:46.080306	admin	EPC generada por IA
9	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:24:17.986647	admin	EPC generada por IA
10	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:37:08.599585	admin	EPC generada por IA
11	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:37:17.565118	admin	EPC generada por IA
12	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:37:23.555741	admin	EPC actualizada (estado: validada) sin firma
13	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:39:25.621462	admin	EPC generada por IA
15	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:41:52.710704	admin	EPC generada por IA
16	e17c8c7d-488c-4e63-8f37-4f1afefa4805	2026-02-06 00:49:08.477719	admin	EPC generada por IA
17	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 00:55:45.233259	admin	EPC creada
19	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 00:56:01.304773	admin	EPC generada por IA
147	3040cd71-cecb-4c0a-8321-5925c981eaa8	2026-02-18 22:59:32.129189	secimino	EPC generada por IA
22	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 01:56:34.593317	admin	EPC generada por IA
23	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 02:20:08.1595	admin	EPC generada por IA
28	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 02:50:11.357912	admin	EPC generada por IA
29	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 02:51:02.579128	admin	EPC generada por IA
32	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 02:55:53.289338	admin	EPC generada por IA
37	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-06 03:26:20.376329	admin	EPC generada por IA
42	048000ec-a84c-412f-84ce-5582681be01a	2026-02-06 12:36:33.153454	admin	EPC generada por IA
43	048000ec-a84c-412f-84ce-5582681be01a	2026-02-06 12:52:00.693389	admin	EPC generada por IA
44	048000ec-a84c-412f-84ce-5582681be01a	2026-02-06 12:59:24.134619	admin	EPC generada por IA
53	048000ec-a84c-412f-84ce-5582681be01a	2026-02-06 16:56:32.923238	admin	EPC generada por IA
140	2a05bbd9-7925-4e26-be7e-c93e8ee81dfb	2026-02-18 22:17:27.022411	secimino	EPC generada por IA
143	5adb306d-73a8-4d2b-bc43-629aec606453	2026-02-18 22:34:15.211617	secimino	EPC actualizada (estado: validada) sin firma
146	3040cd71-cecb-4c0a-8321-5925c981eaa8	2026-02-18 22:58:15.439066	secimino	EPC actualizada (estado: validada) sin firma
63	05bd76a3-5044-4be4-aa01-bda947bf5120	2026-02-06 17:57:52.635614	admin	EPC generada por IA
150	74acffa4-fbd7-44a8-abe4-2d0d29eef853	2026-02-19 05:00:51.140169	admin	EPC actualizada (estado: validada) sin firma
153	30024bfd-34a5-48fb-8dfc-100c027eb8e9	2026-02-20 01:44:13.536798	secimino	EPC generada por IA
160	c75a7d64-e9b4-4fd7-a011-14c3c6d479e1	2026-02-20 02:09:37.748936	secimino	EPC creada
163	15ac7e6b-aa61-4318-92c9-6fd3058d66c0	2026-02-20 02:13:34.295441	secimino	EPC creada
76	c47dc975-b13b-462e-8273-8dc20dae7d3a	2026-02-06 18:53:17.983028	secimino	EPC creada
98	52b16428-dad5-456f-8560-e640ab848d42	2026-02-07 22:29:11.190821	secimino	EPC generada por IA
107	ea432322-a038-4d66-a551-bbd5330a7d29	2026-02-07 22:39:43.671907	secimino	EPC generada por IA
108	ea432322-a038-4d66-a551-bbd5330a7d29	2026-02-07 22:41:18.813833	secimino	EPC actualizada (estado: validada) sin firma
114	fefc8a4f-3e9c-4a67-a121-cedf0d5648da	2026-02-08 03:15:18.448159	secimino	EPC creada
121	44f9e13d-abb0-409f-9434-c444cd5e3458	2026-02-10 21:42:11.644834	admin	EPC generada por IA
136	d722b0c3-e51d-49c0-9323-c7db2ad76824	2026-02-18 22:04:36.861994	secimino	EPC creada
129	4ce3a618-7daa-4454-acb5-3a8030978059	2026-02-14 03:55:58.074507	secimino	EPC creada
174	a71525c4-007f-4977-80b1-2c7e11637c1c	2026-02-22 23:19:48.612852	admin	EPC generada por IA
175	a71525c4-007f-4977-80b1-2c7e11637c1c	2026-02-22 23:25:55.633788	admin	EPC actualizada (estado: validada) firmada por médico
131	4ce3a618-7daa-4454-acb5-3a8030978059	2026-02-14 04:00:40.178702	secimino	EPC actualizada (estado: validada) sin firma
133	2724cfb7-11c1-4697-9b2f-d864edc011a9	2026-02-14 04:04:40.304475	secimino	EPC generada por IA
\.


--
-- Data for Name: patient_status; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.patient_status (patient_id, estado, observaciones, updated_at) FROM stdin;
AINSTEIN_529170	epc_generada	EPC generada (epc_id=d722b0c3-e51d-49c0-9323-c7db2ad76824) a partir de HCE 699635baa7fafdfa859eaf13	2026-02-18 22:04:37.030505
AINSTEIN_380216	epc_generada	EPC generada (epc_id=7b03be10-46cf-4576-9bda-3b37b9c13751) a partir de HCE 69963b97a7fafdfa859eaf19	2026-02-18 22:22:38.745124
AINSTEIN_417995	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-20 01:50:52.530035
AINSTEIN_406793	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-20 02:15:59.309043
AINSTEIN_20580	epc_generada	EPC generada (epc_id=3040cd71-cecb-4c0a-8321-5925c981eaa8) a partir de HCE 699643b4a7fafdfa859eaf6d	2026-02-18 22:56:58.135867
AINSTEIN_380099	epc_generada	EPC generada (epc_id=fa1ef20e-b566-467f-b467-db715d75b4f5) a partir de HCE 696b9484cb0249c72b4147cb	2026-01-30 22:09:52.630029
15a25b2f-f9e2-4fec-ae50-4d7c4cbc812c	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_20347	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378121	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378262	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378413	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378471	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378932	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_379213	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_379311	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_381537	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_381776	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_383433	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_387454	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_401410	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_402006	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_403371	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_409872	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_411729	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_415470	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_427997	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_430173	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_435974	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_438721	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_444893	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_462059	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_463778	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_484660	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_487379	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_500339	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_500599	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_524430	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_524534	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_532721	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_533485	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_535420	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_546749	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_548565	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_549183	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_554729	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_10258	epc_generada	EPC generada (epc_id=86fe8b05-d66e-41e1-b520-ba4b1e230792) a partir de HCE 6973b80d90121eb56a093377	2026-01-30 22:09:52.630029
AINSTEIN_378705	epc_generada	EPC generada (epc_id=dbd660b0-e9ac-4731-8bb0-f489d1c45e35) a partir de HCE 69775a6d90121eb56a093397	2026-01-30 22:09:52.630029
AINSTEIN_383615	epc_generada	EPC generada (epc_id=38ba5741-03f4-4257-8062-87714bcc8c06) a partir de HCE 696be7c8cb0249c72b4147f6	2026-01-30 22:09:52.630029
AINSTEIN_556336	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_558635	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_559674	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_559808	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_559971	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_560058	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_560065	epc_generada	Migrado desde dump	2026-01-30 22:09:52.630029
AINSTEIN_378574	epc_generada	EPC generada (epc_id=048000ec-a84c-412f-84ce-5582681be01a) a partir de HCE 696f9f0a3fdb8bbd92e7e60b	2026-01-30 22:09:52.630029
AINSTEIN_382761	epc_generada	EPC generada (epc_id=0d58c310-a511-4a73-aa2c-9688230acdca) a partir de HCE 69837c3aaa869845acc2cd03	2026-02-04 17:06:16.913695
AINSTEIN_544941	epc_generada	EPC generada (epc_id=2a05bbd9-7925-4e26-be7e-c93e8ee81dfb) a partir de HCE 69963a6aa7fafdfa859eaf17	2026-02-18 22:17:21.442871
AINSTEIN_379457	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 00:28:02.295098
AINSTEIN_405680	epc_generada	EPC generada (epc_id=2724cfb7-11c1-4697-9b2f-d864edc011a9) a partir de HCE 698feec3a7fafdfa859eaded	2026-02-14 04:04:35.922154
AINSTEIN_385518	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-20 01:44:08.132815
AINSTEIN_461196	epc_generada	EPC generada (epc_id=98d35de1-43ab-4fa2-97ad-807629682620) a partir de HCE 6986262c0b3926673f454e6f	2026-02-04 17:23:20.336834
AINSTEIN_546475	epc_generada	EPC generada (epc_id=4656cc86-6b47-4386-a74a-beada573f873) a partir de HCE 6986274a0b3926673f454e72	2026-02-06 17:40:15.796156
AINSTEIN_532743	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-20 02:09:37.926033
AINSTEIN_538874	epc_generada	EPC generada (epc_id=05bd76a3-5044-4be4-aa01-bda947bf5120) a partir de HCE 698628480b3926673f454e75	2026-02-06 18:09:09.417124
AINSTEIN_430261	epc_generada	EPC generada (epc_id=9f83ba8d-21bd-4b6b-86c6-30c587e5a3f6) a partir de HCE 69863740f24c0cf1ac1f11a5	2026-02-06 18:48:06.697701
AINSTEIN_381308	epc_generada	EPC generada (epc_id=c47dc975-b13b-462e-8273-8dc20dae7d3a) a partir de HCE 69863896f24c0cf1ac1f11a8	2026-02-06 18:53:18.463836
AINSTEIN_410471	epc_generada	EPC generada (epc_id=8b3d0d15-cfc1-48ed-a0ab-8c27994c556c) a partir de HCE 6986634df24c0cf1ac1f11af	2026-02-06 21:58:53.174544
AINSTEIN_389468	epc_generada	EPC generada (epc_id=cb273c40-cb44-411f-9003-7b8432f75f7d) a partir de HCE 6986877edaede2ae83adf8e6	2026-02-07 00:31:19.540075
AINSTEIN_464085	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 22:17:59.522796
AINSTEIN_477619	epc_generada	EPC generada (epc_id=ccfbd1d6-16a0-4f59-aae8-fca4bdbcafff) a partir de HCE 6987b879daede2ae83adf942	2026-02-07 22:21:54.469845
AINSTEIN_434312	epc_generada	EPC generada (epc_id=b5da8631-06cb-4716-a24a-279301e880b6) a partir de HCE 6987b8b4daede2ae83adf943	2026-02-07 22:27:32.095299
AINSTEIN_400817	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 22:29:01.139656
AINSTEIN_401694	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 22:31:16.931622
AINSTEIN_387695	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 22:36:09.877046
AINSTEIN_407451	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-07 22:39:33.417067
AINSTEIN_408552	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-08 03:12:24.682826
AINSTEIN_506015	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-08 03:15:18.640249
AINSTEIN_382647	epc_generada	EPC generada (epc_id=44f9e13d-abb0-409f-9434-c444cd5e3458) a partir de HCE 69853a7a0a6aa405fd859ee6	2026-02-10 21:42:06.218881
AINSTEIN_561672	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-14 03:55:58.246504
AINSTEIN_409970	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-20 02:13:34.473946
AINSTEIN_562571	epc_generada	Estado EPC 'validada' seteado por sistema	2026-02-22 23:18:31.50022
\.


--
-- Data for Name: patients; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.patients (id, dni, cuil, obra_social, nro_beneficiario, apellido, nombre, fecha_nacimiento, sexo, estado, telefono, email, domicilio, created_at, updated_at, tenant_id) FROM stdin;
15a25b2f-f9e2-4fec-ae50-4d7c4cbc812c	\N	\N	PAMI UGL VI	150	tj	tj	\N	\N	epc_generada	\N	\N	\N	2026-01-20 02:11:55	2026-01-20 02:28:17	00000000-0000-0000-0000-000000000001
AINSTEIN_20347	\N	\N	\N	\N	AINSTEIN	20347	\N	F	epc_generada	\N	\N	\N	2026-01-22 21:36:25	2026-01-22 21:39:58	00000000-0000-0000-0000-000000000001
AINSTEIN_378121	\N	\N	\N	\N	AINSTEIN	378121	\N	F	epc_generada	\N	\N	\N	2026-01-15 03:15:44	2026-01-15 03:16:05	00000000-0000-0000-0000-000000000001
AINSTEIN_378262	\N	\N	\N	\N	AINSTEIN	378262	\N	M	epc_generada	\N	\N	\N	2026-01-15 13:00:44	2026-01-15 13:54:28	00000000-0000-0000-0000-000000000001
AINSTEIN_378413	\N	\N	\N	\N	AINSTEIN	378413	\N	F	epc_generada	\N	\N	\N	2026-01-15 14:19:04	2026-01-16 04:25:42	00000000-0000-0000-0000-000000000001
AINSTEIN_378471	\N	\N	\N	\N	AINSTEIN	378471	\N	M	epc_generada	\N	\N	\N	2026-01-20 23:36:41	2026-01-21 04:26:28	00000000-0000-0000-0000-000000000001
AINSTEIN_378932	\N	\N	\N	\N	AINSTEIN	378932	\N	M	epc_generada	\N	\N	\N	2026-01-15 12:03:22	2026-01-18 17:15:56	00000000-0000-0000-0000-000000000001
AINSTEIN_379213	\N	\N	\N	\N	AINSTEIN	379213	\N	F	epc_generada	\N	\N	\N	2026-01-16 04:28:41	2026-01-16 04:44:09	00000000-0000-0000-0000-000000000001
AINSTEIN_379311	\N	\N	\N	\N	AINSTEIN	379311	\N	F	epc_generada	\N	\N	\N	2026-01-20 22:42:51	2026-01-20 22:44:03	00000000-0000-0000-0000-000000000001
AINSTEIN_381537	\N	\N	\N	\N	AINSTEIN	381537	\N	F	epc_generada	\N	\N	\N	2026-01-17 12:32:28	2026-01-17 13:00:09	00000000-0000-0000-0000-000000000001
AINSTEIN_381776	\N	\N	\N	\N	AINSTEIN	381776	\N	M	epc_generada	\N	\N	\N	2026-01-16 12:12:08	2026-01-16 12:41:44	00000000-0000-0000-0000-000000000001
AINSTEIN_383433	\N	\N	\N	\N	AINSTEIN	383433	\N	M	epc_generada	\N	\N	\N	2026-01-20 01:58:13	2026-01-20 02:57:09	00000000-0000-0000-0000-000000000001
AINSTEIN_387454	\N	\N	\N	\N	AINSTEIN	387454	\N	F	epc_generada	\N	\N	\N	2026-01-21 13:29:17	2026-01-21 13:38:35	00000000-0000-0000-0000-000000000001
AINSTEIN_401410	\N	\N	\N	\N	AINSTEIN	401410	\N	M	epc_generada	\N	\N	\N	2026-01-16 13:25:01	2026-01-16 14:01:23	00000000-0000-0000-0000-000000000001
AINSTEIN_402006	\N	\N	\N	\N	AINSTEIN	402006	\N	M	epc_generada	\N	\N	\N	2026-01-16 23:43:01	2026-01-20 17:34:39	00000000-0000-0000-0000-000000000001
AINSTEIN_403371	\N	\N	\N	\N	AINSTEIN	403371	\N	F	epc_generada	\N	\N	\N	2026-01-20 12:30:28	2026-01-20 12:30:50	00000000-0000-0000-0000-000000000001
AINSTEIN_409872	\N	\N	\N	\N	AINSTEIN	409872	\N	M	epc_generada	\N	\N	\N	2026-01-21 04:27:50	2026-01-21 04:28:13	00000000-0000-0000-0000-000000000001
AINSTEIN_411729	\N	\N	\N	\N	AINSTEIN	411729	\N	F	epc_generada	\N	\N	\N	2026-01-20 02:58:59	2026-01-20 02:59:44	00000000-0000-0000-0000-000000000001
AINSTEIN_415470	\N	\N	\N	\N	AINSTEIN	415470	\N	M	epc_generada	\N	\N	\N	2026-01-21 13:26:21	2026-01-24 14:48:24	00000000-0000-0000-0000-000000000001
AINSTEIN_427997	\N	\N	\N	\N	AINSTEIN	427997	\N	F	epc_generada	\N	\N	\N	2026-01-20 19:41:38	2026-01-20 19:43:18	00000000-0000-0000-0000-000000000001
AINSTEIN_430173	\N	\N	\N	\N	AINSTEIN	430173	\N	M	epc_generada	\N	\N	\N	2026-01-17 14:59:14	2026-01-17 15:26:18	00000000-0000-0000-0000-000000000001
AINSTEIN_435974	\N	\N	\N	\N	AINSTEIN	435974	\N	M	epc_generada	\N	\N	\N	2026-01-17 13:01:16	2026-01-17 13:12:08	00000000-0000-0000-0000-000000000001
AINSTEIN_438721	\N	\N	\N	\N	AINSTEIN	438721	\N	F	epc_generada	\N	\N	\N	2026-01-17 15:29:22	2026-01-17 15:54:02	00000000-0000-0000-0000-000000000001
AINSTEIN_444893	\N	\N	\N	\N	AINSTEIN	444893	\N	M	epc_generada	\N	\N	\N	2026-01-27 02:54:55	2026-01-27 02:55:26	00000000-0000-0000-0000-000000000001
AINSTEIN_462059	\N	\N	\N	\N	AINSTEIN	462059	\N	M	epc_generada	\N	\N	\N	2026-01-21 13:30:12	2026-01-21 13:30:45	00000000-0000-0000-0000-000000000001
AINSTEIN_463778	\N	\N	\N	\N	AINSTEIN	463778	\N	M	epc_generada	\N	\N	\N	2026-01-16 17:40:01	2026-01-16 18:19:03	00000000-0000-0000-0000-000000000001
AINSTEIN_484660	\N	\N	\N	\N	AINSTEIN	484660	\N	M	epc_generada	\N	\N	\N	2026-01-21 13:25:12	2026-01-21 13:32:39	00000000-0000-0000-0000-000000000001
AINSTEIN_487379	\N	\N	\N	\N	AINSTEIN	487379	\N	F	epc_generada	\N	\N	\N	2026-01-21 13:30:01	2026-01-21 13:39:51	00000000-0000-0000-0000-000000000001
AINSTEIN_500339	\N	\N	\N	\N	AINSTEIN	500339	\N	F	epc_generada	\N	\N	\N	2026-01-16 23:20:35	2026-01-16 23:55:51	00000000-0000-0000-0000-000000000001
AINSTEIN_500599	\N	\N	\N	\N	AINSTEIN	500599	\N	M	epc_generada	\N	\N	\N	2026-01-19 14:12:24	2026-01-19 15:09:26	00000000-0000-0000-0000-000000000001
AINSTEIN_524430	\N	\N	\N	\N	AINSTEIN	524430	\N	M	epc_generada	\N	\N	\N	2026-01-19 22:20:04	2026-01-19 23:06:03	00000000-0000-0000-0000-000000000001
AINSTEIN_524534	\N	\N	\N	\N	AINSTEIN	524534	\N	F	epc_generada	\N	\N	\N	2026-01-19 22:13:03	2026-01-19 22:18:30	00000000-0000-0000-0000-000000000001
AINSTEIN_532721	\N	\N	\N	\N	AINSTEIN	532721	\N	F	epc_generada	\N	\N	\N	2026-01-20 13:23:19	2026-01-20 18:36:53	00000000-0000-0000-0000-000000000001
AINSTEIN_533485	\N	\N	\N	\N	AINSTEIN	533485	\N	F	epc_generada	\N	\N	\N	2026-01-18 14:38:31	2026-01-18 14:41:19	00000000-0000-0000-0000-000000000001
AINSTEIN_535420	\N	\N	\N	\N	AINSTEIN	535420	\N	M	epc_generada	\N	\N	\N	2026-01-23 11:49:34	2026-01-23 12:18:20	00000000-0000-0000-0000-000000000001
AINSTEIN_546749	\N	\N	\N	\N	AINSTEIN	546749	\N	F	epc_generada	\N	\N	\N	2026-01-26 14:49:04	2026-01-26 22:27:15	00000000-0000-0000-0000-000000000001
AINSTEIN_548565	\N	\N	\N	\N	AINSTEIN	548565	\N	F	epc_generada	\N	\N	\N	2026-01-19 17:00:23	2026-01-20 01:56:07	00000000-0000-0000-0000-000000000001
AINSTEIN_549183	\N	\N	\N	\N	AINSTEIN	549183	\N	M	epc_generada	\N	\N	\N	2026-01-19 00:03:16	2026-01-19 00:40:54	00000000-0000-0000-0000-000000000001
AINSTEIN_554729	\N	\N	\N	\N	AINSTEIN	554729	\N	F	epc_generada	\N	\N	\N	2026-01-17 14:23:07	2026-01-17 14:48:53	00000000-0000-0000-0000-000000000001
AINSTEIN_556336	\N	\N	\N	\N	AINSTEIN	556336	\N	M	epc_generada	\N	\N	\N	2026-01-16 12:42:55	2026-01-16 13:09:44	00000000-0000-0000-0000-000000000001
AINSTEIN_558635	\N	\N	\N	\N	AINSTEIN	558635	\N	F	epc_generada	\N	\N	\N	2026-01-20 20:11:17	2026-01-20 21:14:05	00000000-0000-0000-0000-000000000001
AINSTEIN_559674	\N	\N	\N	\N	AINSTEIN	559674	\N	F	epc_generada	\N	\N	\N	2026-01-19 00:41:36	2026-01-19 01:10:33	00000000-0000-0000-0000-000000000001
AINSTEIN_559808	\N	\N	\N	\N	AINSTEIN	559808	\N	F	epc_generada	\N	\N	\N	2026-01-17 13:33:20	2026-01-17 13:53:21	00000000-0000-0000-0000-000000000001
AINSTEIN_559971	\N	\N	\N	\N	AINSTEIN	559971	\N	F	epc_generada	\N	\N	\N	2026-01-20 19:08:50	2026-01-20 19:40:23	00000000-0000-0000-0000-000000000001
AINSTEIN_560058	\N	\N	\N	\N	AINSTEIN	560058	\N	F	epc_generada	\N	\N	\N	2026-01-20 21:22:43	2026-01-20 21:45:41	00000000-0000-0000-0000-000000000001
AINSTEIN_560065	\N	\N	\N	\N	AINSTEIN	560065	\N	F	epc_generada	\N	\N	\N	2026-01-20 21:53:39	2026-01-20 22:24:58	00000000-0000-0000-0000-000000000001
AINSTEIN_10258	\N	\N	\N	\N	AINSTEIN	10258	\N	M	epc_generada	\N	\N	\N	2026-01-23 18:03:57	2026-02-06 15:55:13.410986	00000000-0000-0000-0000-000000000001
AINSTEIN_382761	\N	\N	\N	\N	AINSTEIN	382761	\N	F	epc_generada	\N	\N	\N	2026-02-04 17:04:58.439552	2026-02-04 17:06:20.257357	\N
AINSTEIN_380099	\N	\N	\N	\N	AINSTEIN	380099	\N	M	epc_generada	\N	\N	\N	2026-01-17 13:54:12	2026-02-25 23:01:33.420394	00000000-0000-0000-0000-000000000001
AINSTEIN_383615	\N	\N	\N	\N	AINSTEIN	383615	\N	F	epc_generada	\N	\N	\N	2026-01-17 19:49:28	2026-02-06 19:11:46.842562	00000000-0000-0000-0000-000000000001
AINSTEIN_560894	\N	\N	\N	\N	AINSTEIN	560894	\N	M	internacion	\N	\N	\N	2026-02-06 17:35:15.267919	\N	\N
AINSTEIN_461196	\N	\N	\N	\N	AINSTEIN	461196	\N	F	epc_generada	\N	\N	\N	2026-02-04 17:23:02.67943	2026-02-06 17:36:37.463649	\N
AINSTEIN_418384	\N	\N	\N	\N	AINSTEIN	418384	\N	F	internacion	\N	\N	\N	2026-02-06 17:39:44.595526	\N	\N
AINSTEIN_546475	\N	\N	\N	\N	AINSTEIN	546475	\N	F	epc_generada	\N	\N	\N	2026-02-06 17:39:22.555799	2026-02-06 17:40:18.529789	\N
AINSTEIN_378705	\N	\N	\N	\N	AINSTEIN	378705	\N	M	epc_generada	\N	\N	\N	2026-01-21 13:28:01	2026-02-06 19:06:59.784717	00000000-0000-0000-0000-000000000001
AINSTEIN_378574	\N	\N	\N	\N	AINSTEIN	378574	\N	F	epc_generada	\N	\N	\N	2026-01-20 15:28:01	2026-02-06 17:56:29.417032	00000000-0000-0000-0000-000000000001
AINSTEIN_506015	\N	\N	\N	\N	AINSTEIN	506015	\N	M	epc_generada	\N	\N	\N	2026-02-07 22:17:19.96814	2026-02-12 22:49:06.300571	\N
AINSTEIN_407451	\N	\N	\N	\N	AINSTEIN	407451	\N	M	epc_generada	\N	\N	\N	2026-02-07 22:14:39.228766	2026-02-12 23:19:42.144055	\N
AINSTEIN_561672	\N	\N	\N	\N	AINSTEIN	561672	\N	M	epc_generada	\N	\N	\N	2026-02-14 03:39:10.221667	2026-02-14 04:00:40.173247	\N
AINSTEIN_538874	\N	\N	\N	\N	AINSTEIN	538874	\N	M	epc_generada	\N	\N	\N	2026-02-06 18:05:50.713109	2026-02-06 18:26:40.677037	\N
AINSTEIN_537951	\N	\N	\N	\N	AINSTEIN	537951	\N	M	internacion	\N	\N	\N	2026-02-06 18:47:52.938742	\N	\N
AINSTEIN_430261	\N	\N	\N	\N	AINSTEIN	430261	\N	F	epc_generada	\N	\N	\N	2026-02-06 18:47:28.506533	2026-02-06 18:48:10.09558	\N
AINSTEIN_562571	\N	\N	\N	\N	AINSTEIN	562571	\N	F	epc_generada	\N	\N	\N	2026-02-22 23:17:54.10921	2026-02-22 23:25:55.629059	\N
AINSTEIN_381308	\N	\N	\N	\N	AINSTEIN	381308	\N	F	epc_generada	\N	\N	\N	2026-02-06 18:53:10.451576	2026-02-06 18:53:21.373636	\N
AINSTEIN_410471	\N	\N	\N	\N	AINSTEIN	410471	\N	F	epc_generada	\N	\N	\N	2026-02-06 21:55:25.584043	2026-02-07 00:00:19.78554	\N
AINSTEIN_385518	\N	\N	\N	\N	AINSTEIN	385518	\N	F	epc_generada	\N	\N	\N	2026-02-20 01:37:15.0118	2026-02-25 19:28:30.130404	\N
AINSTEIN_20580	\N	\N	\N	\N	AINSTEIN	20580	\N	F	epc_generada	\N	\N	\N	2026-02-18 22:56:52.559671	2026-02-25 22:02:56.524992	\N
AINSTEIN_529170	\N	\N	\N	\N	AINSTEIN	529170	\N	F	epc_generada	\N	\N	\N	2026-02-18 21:57:14.919547	2026-02-18 22:09:17.272263	\N
AINSTEIN_389468	\N	\N	\N	\N	AINSTEIN	389468	\N	M	epc_generada	\N	\N	\N	2026-02-07 00:29:50.482425	2026-02-07 00:31:22.829761	\N
AINSTEIN_425540	\N	\N	\N	\N	AINSTEIN	425540	\N	M	internacion	\N	\N	\N	2026-02-07 01:46:43.019274	\N	\N
AINSTEIN_417995	\N	\N	\N	\N	AINSTEIN	417995	\N	M	epc_generada	\N	\N	\N	2026-02-20 01:40:36.93802	2026-02-26 22:02:03.814236	\N
AINSTEIN_544941	\N	\N	\N	\N	AINSTEIN	544941	\N	M	epc_generada	\N	\N	\N	2026-02-18 22:17:14.627813	2026-02-18 22:17:27.018993	\N
AINSTEIN_477619	\N	\N	\N	\N	AINSTEIN	477619	\N	F	epc_generada	\N	\N	\N	2026-02-07 22:11:04.989667	2026-02-07 22:21:58.457282	\N
AINSTEIN_532743	\N	\N	\N	\N	AINSTEIN	532743	\N	F	epc_generada	\N	\N	\N	2026-02-20 01:42:41.848457	2026-02-26 23:14:32.113273	\N
AINSTEIN_380216	\N	\N	\N	\N	AINSTEIN	380216	\N	M	epc_generada	\N	\N	\N	2026-02-18 22:22:15.014024	2026-02-18 22:22:44.080131	\N
AINSTEIN_434312	\N	\N	\N	\N	AINSTEIN	434312	\N	M	epc_generada	\N	\N	\N	2026-02-07 22:12:04.843443	2026-02-07 22:28:38.044551	\N
AINSTEIN_408552	\N	\N	\N	\N	AINSTEIN	408552	\N	M	epc_generada	\N	\N	\N	2026-02-07 22:15:31.528457	2026-02-18 22:34:15.206868	\N
AINSTEIN_400817	\N	\N	\N	\N	AINSTEIN	400817	\N	F	epc_generada	\N	\N	\N	2026-02-07 22:12:53.643129	2026-02-07 22:31:12.819251	\N
AINSTEIN_409970	\N	\N	\N	\N	AINSTEIN	409970	\N	F	epc_generada	\N	\N	\N	2026-02-20 02:12:36.571868	2026-02-28 18:47:00.695889	\N
AINSTEIN_406793	\N	\N	\N	\N	AINSTEIN	406793	\N	M	epc_generada	\N	\N	\N	2026-02-20 02:15:44.951263	2026-02-28 19:32:04.312087	\N
AINSTEIN_401694	\N	\N	\N	\N	AINSTEIN	401694	\N	F	epc_generada	\N	\N	\N	2026-02-07 22:13:25.786733	2026-02-07 22:31:40.763012	\N
AINSTEIN_379457	\N	\N	\N	\N	AINSTEIN	379457	\N	F	epc_generada	\N	\N	\N	2026-02-07 00:26:34.826683	2026-02-19 05:00:51.135196	\N
AINSTEIN_405680	\N	\N	\N	\N	AINSTEIN	405680	\N	M	epc_generada	\N	\N	\N	2026-02-14 03:40:51.013196	2026-02-19 05:37:21.192362	\N
AINSTEIN_387695	\N	\N	\N	\N	AINSTEIN	387695	\N	F	epc_generada	\N	\N	\N	2026-02-07 22:14:04.477411	2026-02-08 03:12:07.726272	\N
AINSTEIN_382647	\N	\N	\N	\N	AINSTEIN	382647	\N	F	epc_generada	\N	\N	\N	2026-02-10 21:41:59.715108	2026-02-10 22:21:49.247138	\N
AINSTEIN_464085	\N	\N	\N	\N	AINSTEIN	464085	\N	M	epc_generada	\N	\N	\N	2026-02-07 22:16:36.549788	2026-02-11 23:29:10.866569	\N
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.roles (id, name) FROM stdin;
1	admin
2	medico
3	viewer
\.


--
-- Data for Name: tenant_api_keys; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tenant_api_keys (id, tenant_id, key_hash, key_prefix, name, is_active, created_at, last_used_at, expires_at) FROM stdin;
\.


--
-- Data for Name: tenants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tenants (id, code, name, logo_url, contact_email, is_active, created_at, updated_at, webhook_url, api_rate_limit, integration_type, external_endpoint, external_token, external_auth_type, external_headers, allowed_scopes, webhook_secret, notes, display_rules) FROM stdin;
00000000-0000-0000-0000-000000000001	markey	Clinica Markey	\N	\N	t	2026-01-30 22:04:51.968949	2026-02-05 13:42:29.214066	\N	\N	inbound	https://ainstein1.markeyoci.com.ar/obtener	lkjnlkrw8eonlrhwewasdkamrweqwepomqwqnwedxcipofpifnfgmhltryeqweqwexgaqw9308252tjfiskml	bearer	{"app": "AInstein", "api_key": "1f7995f7-4131-41a1-b104-f51d2179dcfe", "http_method": "GET", "timeout_seconds": 60}	read_patients,read_epc	\N	Migrado desde .env el 2026-02-02T23:19:40.369343	{"excluded_sections": ["enfermeria", "epicrisis", "higiene"]}
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, username, password_hash, full_name, email, role_id, is_active, created_at, updated_at, tenant_id) FROM stdin;
042bcfb6-b8fa-4c35-b352-cd45eb90a014	Mroverano	$2b$12$2EeZm9IhmzF0MC0EgN504ecSh7ck9IPYx6PMSl7.IhJgH4MIyxgUm	Melisa Roverano	melirove@gmail.com	2	t	2025-12-22 10:45:57	\N	00000000-0000-0000-0000-000000000001
383bcfc0-961e-4e2a-b55d-a7eff3bef950	test	$2b$12$2Hplfzk50ztMkbE2Ri5Qne3ZvB/pCugbR1xZnp8o9wV3xBR8p063y	Medico Test	test@gmail.com	2	t	2026-01-21 12:37:56	\N	00000000-0000-0000-0000-000000000001
751fce62-c772-41fa-ae47-1eaa344676ce	MEConsejero	$2b$12$3U4z1.Cn7c8c49owD56WH.s/diwTxCy9/UWkJ58FQVXtUjfg8LfD.	Maria Eugenia Consejero	consejero.m.e@gmail.com	2	t	2025-12-22 10:41:52	\N	00000000-0000-0000-0000-000000000001
8fd9a9f1-3f12-48b0-a3a3-b44927920bf0	aaltamirano	$2b$12$KYhwEFNIwLUIZJ7pGaSg7uhg4UQ0bC98zsLSezB6fmtYTPbPcJs8q	Alan Altamirano	alangaltamirano@gmail.com	2	t	2026-01-15 03:01:48	\N	00000000-0000-0000-0000-000000000001
a72c21ae-bd60-4863-8aa3-177eaa2864e5	Hbritto	$2b$12$uKh0pCIVOstSbHzbKjuMRuw63Wv9ejFITnlKTvBki/TG8oufh2xmy	Heyde Britto	heydebritto17@gmail.com	2	t	2025-12-22 10:44:09	\N	00000000-0000-0000-0000-000000000001
ed6e465d-d60c-4991-9a75-f3a14e304ebb	Nelias	$2b$12$Mhl9NUcjyplOkKHFxVafieuCa6K8MkvVM12rfmc71zLODNj2pCRyq	Nahuel Elias	nahuelelias@gmail.com	2	t	2025-12-22 10:33:44	\N	00000000-0000-0000-0000-000000000001
f7f1ddbf-e458-46c2-abff-d62b63de39f9	admin	$2b$12$dR1XGD2b0pM2jGTWNFgjCe3sRZr66SJ9Pm73V01KvYvPRx53IuBGS	Administrador General	soporte@zeron.com.ar	1	t	2025-11-19 01:12:11	2025-11-21 12:32:52	00000000-0000-0000-0000-000000000001
1373409e-4ee4-4b83-9f2e-78bc7e62124c	pdimitroff	$2b$12$t1/xEAJNRlvyOizdFflIUuJJ9J7lgyEDejrAi/YNWHZphIQR9Hvbi	Dimitroff, Pablo	sebasank@gmail.com	1	t	2025-11-22 00:15:29	2025-12-02 19:28:48	00000000-0000-0000-0000-000000000001
3a1a502e-3816-43e2-b862-108c8b8919a7	secimino	$2b$12$XcnHolce7u4sjtcNxbn8/uLlAgFVigK.rufTFTWCvilmbBicAshqO	Cimino, Sebastián	sebastian@zeron.com.ar	1	t	2026-01-17 06:22:14	\N	00000000-0000-0000-0000-000000000001
7ddbd790-4bf7-4451-b7be-cc0eb851707a	gustavop	$2b$12$7f5kCkPxaVISFm7d.7/vmuZgLHZvomtA7BdYfBh6OKG3Cije1.SVi	Petroni, Gustavo	gpetroni@grupogamma.com	1	t	2025-12-09 04:50:16	\N	00000000-0000-0000-0000-000000000001
b75c2f89-1057-427a-9478-6e5f6aebbacf	zeron	$2b$12$wazpYeK5lM9tPd5fAt7aReERCzkU81pqi4C8zSOmLciagApsGthVK	Antonioli, Renzo	rantonioli@zeron.com.ar	1	t	2026-01-16 13:21:26	\N	00000000-0000-0000-0000-000000000001
4a26f837-9fd7-4efb-ba1e-1909ebf5feac	cgeiger	$2b$12$Uyi62OItl4UjjOOr1ff2l.uhrta751.cApi/eRzXIlINPQkppg0XC	Geiger, Carla	Carlasgeiger@gmail.com	2	t	2026-02-10 12:48:36.47669	\N	\N
\.


--
-- Name: branding_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.branding_id_seq', 1, false);


--
-- Name: epc_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.epc_events_id_seq', 183, true);


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.roles_id_seq', 1, false);


--
-- Name: abac_audit_log abac_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.abac_audit_log
    ADD CONSTRAINT abac_audit_log_pkey PRIMARY KEY (id);


--
-- Name: abac_policies abac_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.abac_policies
    ADD CONSTRAINT abac_policies_pkey PRIMARY KEY (id);


--
-- Name: admissions admissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions
    ADD CONSTRAINT admissions_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: branding branding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branding
    ADD CONSTRAINT branding_pkey PRIMARY KEY (id);


--
-- Name: epc_events epc_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc_events
    ADD CONSTRAINT epc_events_pkey PRIMARY KEY (id);


--
-- Name: epc epc_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_pkey PRIMARY KEY (id);


--
-- Name: patient_status patient_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_status
    ADD CONSTRAINT patient_status_pkey PRIMARY KEY (patient_id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: tenant_api_keys tenant_api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_api_keys
    ADD CONSTRAINT tenant_api_keys_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_code_key UNIQUE (code);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_abac_policies_tenant_name_active; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_abac_policies_tenant_name_active ON public.abac_policies USING btree (tenant_id, name) WHERE (is_active = true);


--
-- Name: idx_patients_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_patients_tenant_id ON public.patients USING btree (tenant_id);


--
-- Name: idx_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_tenant_id ON public.users USING btree (tenant_id);


--
-- Name: ix_abac_audit_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_abac_audit_log_created_at ON public.abac_audit_log USING btree (created_at);


--
-- Name: ix_abac_audit_log_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_abac_audit_log_tenant_id ON public.abac_audit_log USING btree (tenant_id);


--
-- Name: ix_abac_audit_log_trace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_abac_audit_log_trace_id ON public.abac_audit_log USING btree (trace_id);


--
-- Name: admissions admissions_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions
    ADD CONSTRAINT admissions_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;


--
-- Name: admissions admissions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions
    ADD CONSTRAINT admissions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: branding branding_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branding
    ADD CONSTRAINT branding_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: epc epc_admission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_admission_id_fkey FOREIGN KEY (admission_id) REFERENCES public.admissions(id);


--
-- Name: epc epc_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: epc epc_last_edited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_last_edited_by_fkey FOREIGN KEY (last_edited_by) REFERENCES public.users(id);


--
-- Name: epc epc_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;


--
-- Name: epc epc_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epc
    ADD CONSTRAINT epc_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: patient_status patient_status_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_status
    ADD CONSTRAINT patient_status_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;


--
-- Name: patients patients_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: tenant_api_keys tenant_api_keys_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_api_keys
    ADD CONSTRAINT tenant_api_keys_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: users users_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: abac_audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.abac_audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: abac_policies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.abac_policies ENABLE ROW LEVEL SECURITY;

--
-- Name: patients; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;

--
-- Name: abac_audit_log rls_abac_audit_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY rls_abac_audit_tenant ON public.abac_audit_log USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));


--
-- Name: abac_policies rls_abac_policies_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY rls_abac_policies_tenant ON public.abac_policies USING (((tenant_id IS NULL) OR (tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)));


--
-- Name: patients rls_patients_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY rls_patients_tenant ON public.patients USING (((tenant_id IS NULL) OR ((tenant_id)::text = NULLIF(current_setting('app.tenant_id'::text, true), ''::text))));


--
-- Name: users rls_users_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY rls_users_tenant ON public.users USING (((tenant_id IS NULL) OR ((tenant_id)::text = NULLIF(current_setting('app.tenant_id'::text, true), ''::text))));


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 6JnMwKTpURvhwofjqwSBTbnZGYVXehHF5d6A8IlaLfZDoJEs3YoqeF82kSMsy9l

