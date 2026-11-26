"""Automated Python code validation and targeted single-block repair pipeline.

Pipeline:
  Code -> AST syntax & compile -> Undefined identifier analysis
       -> Isolated subprocess execution (when stdlib-safe) -> Validated result.
"""
from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from app.ai.models.model_router import model_router
from app.core.logging import logger
from app.services.code_sandbox import execute_python_sandbox, validate_python_code

_BUILTIN_NAMES: Set[str] = set(dir(builtins)) | {"__name__", "__doc__", "True", "False", "None", "Ellipsis"}


@dataclass
class CodeValidationResult:
    valid: bool
    syntax_ok: bool
    undefined_names: List[str]
    runtime_ok: Optional[bool]
    error_message: Optional[str] = None
    stdout: str = ""
    compile_ok: bool = False
    scope_ok: bool = False
    output_verified: Optional[bool] = None
    repaired: bool = False
    final_accepted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "syntax_ok": self.syntax_ok,
            "compile_ok": self.compile_ok,
            "scope_ok": self.scope_ok,
            "undefined_names": self.undefined_names,
            "runtime_ok": self.runtime_ok,
            "output_verified": self.output_verified,
            "repaired": self.repaired,
            "final_accepted": self.final_accepted,
            "error_message": self.error_message,
            "stdout": self.stdout,
        }


class _ScopeAnalyzer(ast.NodeVisitor):
    """Scope-aware AST visitor to detect genuinely undefined identifiers without false positives."""

    def __init__(self) -> None:
        self.scopes: List[Set[str]] = [set(_BUILTIN_NAMES)]
        self.undefined: List[str] = []

    def _define(self, name: str) -> None:
        if name:
            self.scopes[-1].add(name)

    def _is_defined(self, name: str) -> bool:
        return any(name in scope for scope in reversed(self.scopes))

    def _collect_target(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self._define(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._collect_target(elt)
        elif isinstance(target, ast.Starred):
            self._collect_target(target.value)

    def _collect_pattern(self, pattern: ast.AST) -> None:
        if hasattr(ast, "MatchAs") and isinstance(pattern, ast.MatchAs):
            if pattern.name:
                self._define(pattern.name)
            if pattern.pattern:
                self._collect_pattern(pattern.pattern)
        elif hasattr(ast, "MatchSequence") and isinstance(pattern, ast.MatchSequence):
            for p in pattern.patterns:
                self._collect_pattern(p)
        elif hasattr(ast, "MatchMapping") and isinstance(pattern, ast.MatchMapping):
            for p in pattern.patterns:
                self._collect_pattern(p)
            if pattern.rest:
                self._define(pattern.rest)
        elif hasattr(ast, "MatchClass") and isinstance(pattern, ast.MatchClass):
            for p in pattern.patterns + pattern.kwd_patterns:
                self._collect_pattern(p)
        elif hasattr(ast, "MatchStar") and isinstance(pattern, ast.MatchStar) and pattern.name:
            self._define(pattern.name)
        elif hasattr(ast, "MatchOr") and isinstance(pattern, ast.MatchOr):
            for p in pattern.patterns:
                self._collect_pattern(p)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._define(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self._define(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._define(name)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self._define(name)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self._collect_target(target)
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                self.visit(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            self.visit(node.value)
        if node.annotation:
            self.visit(node.annotation)
        self._collect_target(node.target)
        if isinstance(node.target, (ast.Attribute, ast.Subscript)):
            self.visit(node.target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self.visit(node.target)
        self._collect_target(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._collect_target(node.target)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._collect_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit_For(node)  # type: ignore[arg-type]

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._collect_target(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.visit_With(node)  # type: ignore[arg-type]

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type:
            self.visit(node.type)
        if node.name:
            self._define(node.name)
        for stmt in node.body:
            self.visit(stmt)

    def visit_Match(self, node: Any) -> None:
        self.visit(node.subject)
        for case in node.cases:
            self._collect_pattern(case.pattern)
            if case.guard:
                self.visit(case.guard)
            for stmt in case.body:
                self.visit(stmt)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for dec in node.decorator_list:
            self.visit(dec)
        for base in node.bases:
            self.visit(base)
        for kw in node.keywords:
            self.visit(kw.value)
        self._define(node.name)
        self.scopes.append(set())
        for stmt in node.body:
            self.visit(stmt)
        self.scopes.pop()

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for dec in node.decorator_list:
            self.visit(dec)
        for d in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            self.visit(d)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        if node.returns:
            self.visit(node.returns)

        self._define(node.name)
        fn_scope: Set[str] = set()
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            fn_scope.add(arg.arg)
        if node.args.vararg:
            fn_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            fn_scope.add(node.args.kwarg.arg)

        self.scopes.append(fn_scope)
        for stmt in node.body:
            self.visit(stmt)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for d in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            self.visit(d)
        lam_scope: Set[str] = set()
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            lam_scope.add(arg.arg)
        if node.args.vararg:
            lam_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            lam_scope.add(node.args.kwarg.arg)
        self.scopes.append(lam_scope)
        self.visit(node.body)
        self.scopes.pop()

    def _visit_comprehension(self, generators: List[ast.comprehension], elts: List[ast.AST]) -> None:
        if generators:
            self.visit(generators[0].iter)
        self.scopes.append(set())
        for idx, gen in enumerate(generators):
            if idx > 0:
                self.visit(gen.iter)
            self._collect_target(gen.target)
            for cond in gen.ifs:
                self.visit(cond)
        for elt in elts:
            self.visit(elt)
        self.scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, [node.key, node.value])

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if not self._is_defined(node.id) and node.id not in self.undefined:
                self.undefined.append(node.id)


class CodeValidationPipeline:
    """Validates generated Python snippets without ever executing untrusted code in-process."""

    @staticmethod
    def find_undefined_identifiers(code: str) -> List[str]:
        """Scope-aware static AST analysis to catch genuine undefined identifiers."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        analyzer = _ScopeAnalyzer()
        analyzer.visit(tree)
        return analyzer.undefined

    @classmethod
    def validate_code_block(
        cls,
        code: str,
        run_in_sandbox: bool = True,
        expected_output: Optional[str] = None,
    ) -> CodeValidationResult:
        cleaned = (code or "").strip()
        if not cleaned:
            return CodeValidationResult(
                valid=False,
                syntax_ok=False,
                undefined_names=[],
                runtime_ok=None,
                error_message="Empty code block",
                compile_ok=False,
                scope_ok=False,
                final_accepted=False,
            )

        # 1. AST syntax check
        try:
            tree = ast.parse(cleaned)
        except SyntaxError as exc:
            return CodeValidationResult(
                valid=False,
                syntax_ok=False,
                undefined_names=[],
                runtime_ok=None,
                error_message=f"SyntaxError at line {exc.lineno}: {exc.msg}",
                compile_ok=False,
                scope_ok=False,
                final_accepted=False,
            )

        # 2. Bytecode compilation check
        try:
            compile(tree, "<lesson_example>", "exec")
        except Exception as exc:
            return CodeValidationResult(
                valid=False,
                syntax_ok=True,
                undefined_names=[],
                runtime_ok=None,
                error_message=f"CompileError: {exc}",
                compile_ok=False,
                scope_ok=False,
                final_accepted=False,
            )

        # 3. Scope-aware static identifier check
        undef = cls.find_undefined_identifiers(cleaned)
        if undef:
            return CodeValidationResult(
                valid=False,
                syntax_ok=True,
                undefined_names=undef,
                runtime_ok=None,
                error_message=f"Undefined identifier(s): {', '.join(undef[:5])}",
                compile_ok=True,
                scope_ok=False,
                final_accepted=False,
            )

        # 4. Isolated subprocess sandbox check (when sandbox-allowed imports)
        if run_in_sandbox:
            sandbox_allowed, _ = validate_python_code(cleaned)
            if sandbox_allowed:
                res = execute_python_sandbox(cleaned, test_cases=[], timeout_seconds=3)
                stdout = res.get("stdout", "")
                if not res.get("passed"):
                    return CodeValidationResult(
                        valid=False,
                        syntax_ok=True,
                        undefined_names=[],
                        runtime_ok=False,
                        error_message=res.get("stderr") or "Sandbox execution failed",
                        stdout=stdout,
                        compile_ok=True,
                        scope_ok=True,
                        output_verified=False if expected_output is not None else None,
                        final_accepted=False,
                    )
                output_ok: Optional[bool] = None
                if expected_output is not None:
                    output_ok = expected_output.strip() in stdout
                    if not output_ok:
                        return CodeValidationResult(
                            valid=False,
                            syntax_ok=True,
                            undefined_names=[],
                            runtime_ok=True,
                            error_message=f"Expected output '{expected_output}' not found in stdout",
                            stdout=stdout,
                            compile_ok=True,
                            scope_ok=True,
                            output_verified=False,
                            final_accepted=False,
                        )
                return CodeValidationResult(
                    valid=True,
                    syntax_ok=True,
                    undefined_names=[],
                    runtime_ok=True,
                    stdout=stdout,
                    compile_ok=True,
                    scope_ok=True,
                    output_verified=output_ok,
                    final_accepted=True,
                )

        # Framework imports (e.g. fastapi, pydantic) pass AST + compile + scope checks
        return CodeValidationResult(
            valid=True,
            syntax_ok=True,
            undefined_names=[],
            runtime_ok=None,
            compile_ok=True,
            scope_ok=True,
            output_verified=None,
            final_accepted=True,
        )

    @classmethod
    async def repair_code_block(
        cls,
        code: str,
        error_message: str,
        topic_title: str,
        max_attempts: int = 1,
    ) -> Tuple[str, CodeValidationResult]:
        """Targeted minimal repair of ONLY the failing Python snippet (max 1-2 attempts)."""
        current = code
        result = cls.validate_code_block(current)
        if result.valid:
            return current, result

        for attempt in range(max_attempts):
            repair_prompt = (
                f"Fix ONLY the error in this Python snippet for '{topic_title}'.\n"
                f"Error: {result.error_message or error_message}\n"
                "Rules: Include all required imports, define every variable/function used, keep it concise and runnable.\n"
                "Return ONLY a single ```python code block with no extra prose.\n\n"
                f"```python\n{current}\n```"
            )
            try:
                res = await model_router.generate(
                    prompt=repair_prompt,
                    task_type="summary",
                    temperature=0.1,
                    max_tokens=320,
                )
                raw = (res.get("content") or "").strip()
                m = re.search(r"```(?:python)?\n(.*?)```", raw, flags=re.DOTALL)
                candidate = (m.group(1) if m else raw).strip()
                if candidate:
                    check = cls.validate_code_block(candidate)
                    if check.valid:
                        check.repaired = True
                        check.final_accepted = True
                        return candidate, check
                    current = candidate
                    result = check
            except Exception as exc:
                logger.debug(f"Targeted code repair attempt {attempt + 1} failed: {exc}")
                break

        return current, result
