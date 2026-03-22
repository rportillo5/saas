module.exports = [
"[project]/node_modules/@clerk/nextjs/dist/esm/app-router/client/keyless-creator-reader.js [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "KeylessCreatorOrReader",
    ()=>KeylessCreatorOrReader
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$navigation$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/navigation.js [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f40$clerk$2f$nextjs$2f$dist$2f$esm$2f$app$2d$router$2f$keyless$2d$actions$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/@clerk/nextjs/dist/esm/app-router/keyless-actions.js [ssr] (ecmascript)");
;
;
;
;
const KeylessCreatorOrReader = (props)=>{
    var _a;
    const { children } = props;
    const segments = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$navigation$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["useSelectedLayoutSegments"])();
    const isNotFoundRoute = ((_a = segments[0]) == null ? void 0 : _a.startsWith("/_not-found")) || false;
    const [state, fetchKeys] = __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["default"].useActionState(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f40$clerk$2f$nextjs$2f$dist$2f$esm$2f$app$2d$router$2f$keyless$2d$actions$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["createOrReadKeylessAction"], null);
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (isNotFoundRoute) {
            return;
        }
        __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["default"].startTransition(()=>{
            fetchKeys();
        });
    }, [
        isNotFoundRoute
    ]);
    if (!__TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["default"].isValidElement(children)) {
        return children;
    }
    return __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["default"].cloneElement(children, {
        key: state == null ? void 0 : state.publishableKey,
        publishableKey: state == null ? void 0 : state.publishableKey,
        __internal_keyless_claimKeylessApplicationUrl: state == null ? void 0 : state.claimUrl,
        __internal_keyless_copyInstanceKeysUrl: state == null ? void 0 : state.apiKeysUrl,
        __internal_bypassMissingPublishableKey: true
    });
};
;
 //# sourceMappingURL=keyless-creator-reader.js.map
}),
];

//# sourceMappingURL=a9bf9_%40clerk_nextjs_dist_esm_app-router_client_keyless-creator-reader_e7fc2e94.js.map