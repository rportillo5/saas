"use client"

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useAuth } from '@clerk/nextjs';
import DatePicker from 'react-datepicker';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { Protect, PricingTable, UserButton } from '@clerk/nextjs';

function ConsultationForm() {
    const { getToken } = useAuth();

    // Form state
    const [patientName, setPatientName] = useState('');
    const [visitDate, setVisitDate] = useState<Date | null>(new Date());
    const [specialty, setSpecialty] = useState('');
    const [notes, setNotes] = useState('');

    // Streaming state
    const [output, setOutput] = useState('');
    const [billingCodes, setBillingCodes] = useState<{code: string; description: string}[]>([]);
    const [emLevel, setEmLevel] = useState<{
        code: string; patient_type: string; mdm_level: string;
        problems: string; data: string; risk: string; justification: string;
    } | null>(null);
    const [phiProtected, setPhiProtected] = useState(false);
    const [loading, setLoading] = useState(false);
    const [specialtyMismatch, setSpecialtyMismatch] = useState('');

    function handleClear() {
        setPatientName('');
        setVisitDate(new Date());
        setSpecialty('');
        setNotes('');
        setOutput('');
        setBillingCodes([]);
        setEmLevel(null);
        setPhiProtected(false);
        setSpecialtyMismatch('');
        setLoading(false);
    }

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setOutput('');
        setBillingCodes([]);
        setEmLevel(null);
        setPhiProtected(false);
        setSpecialtyMismatch('');
        setLoading(true);

        const jwt = await getToken();
        if (!jwt) {
            setOutput('Authentication required');
            setLoading(false);
            return;
        }

        const controller = new AbortController();
        let buffer = '';

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
        await fetchEventSource(`${apiUrl}/api`, {
            signal: controller.signal,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${jwt}`,
            },
            body: JSON.stringify({
                patient_name: patientName,
                date_of_visit: visitDate?.toISOString().slice(0, 10),
                specialty,
                notes,
            }),
            onmessage(ev) {
                buffer += ev.data;

                // Check for specialty mismatch
                const mismatchStart = '<!-- SPECIALTY_MISMATCH -->';
                const mismatchEnd = '<!-- /SPECIALTY_MISMATCH -->';
                const mismatchStartIdx = buffer.indexOf(mismatchStart);
                const mismatchEndIdx = buffer.indexOf(mismatchEnd);
                if (mismatchStartIdx !== -1 && mismatchEndIdx !== -1) {
                    const reason = buffer.slice(mismatchStartIdx + mismatchStart.length, mismatchEndIdx).trim();
                    setSpecialtyMismatch(reason);
                    setLoading(false);
                    controller.abort();
                    return;
                }

                // Helper to extract and parse a marker block
                const parseMarker = (buf: string, start: string, end: string) => {
                    const s = buf.indexOf(start);
                    const e = buf.indexOf(end);
                    if (s !== -1 && e !== -1) {
                        const json = buf.slice(s + start.length, e).trim();
                        try { return JSON.parse(json); } catch { return null; }
                    }
                    return null;
                };

                // Parse billing codes
                const billingData = parseMarker(buffer, '<!-- BILLING_CODES_START -->', '<!-- BILLING_CODES_END -->');
                if (billingData) setBillingCodes(billingData);

                // Parse E&M level
                const emData = parseMarker(buffer, '<!-- EM_LEVEL_START -->', '<!-- EM_LEVEL_END -->');
                if (emData) setEmLevel(emData);

                // Parse PHI status
                const phiData = parseMarker(buffer, '<!-- PHI_STATUS_START -->', '<!-- PHI_STATUS_END -->');
                if (phiData) setPhiProtected(phiData.phi_detected);

                // Display text = everything before the first marker
                const markerStarts = [
                    '<!-- BILLING_CODES_START -->',
                    '<!-- EM_LEVEL_START -->',
                    '<!-- PHI_STATUS_START -->',
                ].map(tag => buffer.indexOf(tag)).filter(i => i !== -1);

                if (markerStarts.length > 0) {
                    setOutput(buffer.slice(0, Math.min(...markerStarts)).trim());
                } else {
                    setOutput(buffer);
                }
            },
            onclose() { 
                setLoading(false); 
            },
            onerror(err) {
                console.error('SSE error:', err);
                controller.abort();
                setLoading(false);
            },
        });
    }

    return (
        <div className="container mx-auto px-4 py-12 max-w-3xl">
            <h1 className="text-4xl font-bold text-gray-900 dark:text-gray-100 mb-8">
                Consultation Notes
            </h1>

            <form onSubmit={handleSubmit} className="space-y-6 bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
                <div className="space-y-2">
                    <label htmlFor="patient" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Patient Name
                    </label>
                    <input
                        id="patient"
                        type="text"
                        required
                        value={patientName}
                        onChange={(e) => setPatientName(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        placeholder="Enter patient's full name"
                    />
                </div>

                <div className="space-y-2">
                    <label htmlFor="date" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Date of Visit
                    </label>
                    <DatePicker
                        id="date"
                        selected={visitDate}
                        onChange={(d: Date | null) => setVisitDate(d)}
                        dateFormat="yyyy-MM-dd"
                        placeholderText="Select date"
                        required
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    />
                </div>

                <div className="space-y-2">
                    <label htmlFor="specialty" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Specialty
                    </label>
                    <select
                        id="specialty"
                        required
                        value={specialty}
                        onChange={(e) => setSpecialty(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    >
                        <option value="">Select a specialty</option>
                        <option value="General Practice">General Practice</option>
                        <option value="Cardiology">Cardiology</option>
                        <option value="Dermatology">Dermatology</option>
                        <option value="Endocrinology">Endocrinology</option>
                        <option value="Gastroenterology">Gastroenterology</option>
                        <option value="Neurology">Neurology</option>
                        <option value="Obstetrics & Gynecology">Obstetrics & Gynecology</option>
                        <option value="Oncology">Oncology</option>
                        <option value="Ophthalmology">Ophthalmology</option>
                        <option value="Orthopedics">Orthopedics</option>
                        <option value="Pediatrics">Pediatrics</option>
                        <option value="Psychiatry">Psychiatry</option>
                        <option value="Pulmonology">Pulmonology</option>
                        <option value="Rheumatology">Rheumatology</option>
                        <option value="Urology">Urology</option>
                    </select>
                </div>

                <div className="space-y-2">
                    <label htmlFor="notes" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Consultation Notes
                    </label>
                    <textarea
                        id="notes"
                        required
                        rows={8}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        placeholder="Enter detailed consultation notes..."
                    />
                </div>

                <div className="flex gap-3">
                    <button
                        type="submit"
                        disabled={loading}
                        className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200"
                    >
                        {loading ? (
                            <span className="inline-flex items-center justify-center gap-2">
                                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                <span className="animate-pulse">Generating Summary...</span>
                            </span>
                        ) : 'Generate Summary'}
                    </button>
                    <button
                        type="button"
                        onClick={handleClear}
                        className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-700 dark:text-gray-200 font-semibold py-3 px-6 rounded-lg transition-colors duration-200"
                    >
                        Clear
                    </button>
                </div>
            </form>

            {specialtyMismatch && (
                <div className="mt-8 bg-amber-50 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-xl shadow-lg p-6">
                    <div className="flex items-start gap-3">
                        <span className="text-amber-600 dark:text-amber-400 text-2xl leading-none">&#9888;</span>
                        <div>
                            <h3 className="text-lg font-semibold text-amber-800 dark:text-amber-300 mb-1">
                                Specialty Mismatch
                            </h3>
                            <p className="text-amber-700 dark:text-amber-400">
                                {specialtyMismatch}
                            </p>
                            <p className="text-sm text-amber-600 dark:text-amber-500 mt-2">
                                Please verify the selected specialty matches the consultation notes and try again.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {output && (
                <section className="mt-8 bg-gray-50 dark:bg-gray-800 rounded-xl shadow-lg p-8">
                    {phiProtected && (
                        <div className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 px-3 py-1.5 rounded-full">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            PHI Protected
                        </div>
                    )}

                    <div className="markdown-content prose prose-blue dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                            {output}
                        </ReactMarkdown>
                    </div>

                    {emLevel && (
                        <div className="mt-8 border-t border-gray-200 dark:border-gray-700 pt-6">
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900 text-purple-600 dark:text-purple-300 text-sm font-bold">E</span>
                                E&M Service Level
                            </h3>
                            <div className="bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 p-5">
                                <div className="flex items-center gap-4 mb-4">
                                    <span className="text-3xl font-bold font-mono text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-900/50 px-4 py-2 rounded-lg">
                                        {emLevel.code}
                                    </span>
                                    <div>
                                        <p className="font-semibold text-gray-900 dark:text-gray-100">
                                            {emLevel.patient_type} Patient
                                        </p>
                                        <p className="text-sm text-gray-600 dark:text-gray-400">
                                            {emLevel.mdm_level} Medical Decision Making
                                        </p>
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Problems</p>
                                        <p className="text-sm text-gray-800 dark:text-gray-200">{emLevel.problems}</p>
                                    </div>
                                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Data</p>
                                        <p className="text-sm text-gray-800 dark:text-gray-200">{emLevel.data}</p>
                                    </div>
                                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Risk</p>
                                        <p className="text-sm text-gray-800 dark:text-gray-200">{emLevel.risk}</p>
                                    </div>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400 italic">{emLevel.justification}</p>
                                <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">Suggested E&M level &mdash; verify before billing</p>
                            </div>
                        </div>
                    )}

                    {billingCodes.length > 0 && (
                        <div className="mt-8 border-t border-gray-200 dark:border-gray-700 pt-6">
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-sm font-bold">$</span>
                                Medical Billing Codes
                            </h3>
                            <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white">
                                            <th className="px-4 py-3 text-left font-semibold w-28">Code</th>
                                            <th className="px-4 py-3 text-left font-semibold">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {billingCodes.map((item, i) => (
                                            <tr
                                                key={item.code}
                                                className={i % 2 === 0 ? 'bg-white dark:bg-gray-700' : 'bg-gray-100 dark:bg-gray-800'}
                                            >
                                                <td className="px-4 py-3 font-mono font-semibold !text-blue-700 dark:!text-blue-400">{item.code}</td>
                                                <td className="px-4 py-3 !text-black dark:!text-white">{item.description}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </section>
            )}
        </div>
    );
}

export default function Product() {
    return (
        <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
            {/* Top Navigation */}
            <div className="absolute top-4 left-4">
                <Link
                    href="/"
                    className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 font-medium transition-colors"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                    </svg>
                    Home
                </Link>
            </div>
            <div className="absolute top-4 right-4">
                <UserButton showName={true} />
            </div>

            {/* Subscription Protection */}
            <Protect
                plan="premium_subscription"
                fallback={
                    <div className="container mx-auto px-4 py-12">
                        <header className="text-center mb-12">
                            <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-4">
                                Healthcare Professional Plan
                            </h1>
                            <p className="text-gray-600 dark:text-gray-400 text-lg mb-8">
                                Streamline your patient consultations with AI-powered summaries
                            </p>
                        </header>
                        <div className="max-w-4xl mx-auto">
                            <PricingTable />
                        </div>
                    </div>
                }
            >
                <ConsultationForm />
            </Protect>
        </main>
    );
}