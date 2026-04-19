"""
CLI Entry Point

autonomous-creator 명령줄 인터페이스
"""
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional, List
from pathlib import Path

app = typer.Typer(
    name="autonomous",
    help="AI-powered multi-language short video generator"
)
console = Console()


@app.command()
def create(
    title: str = typer.Option(None, "--title", "-t", help="스토리 제목"),
    content: str = typer.Option(None, "--content", "-c", help="스토리 내용"),
    keywords: List[str] = typer.Option([], "--keyword", "-k", help="키워드"),
    language: str = typer.Option("ko", "--lang", "-l", help="언어 (ko/th/en/ja/zh)"),
    preset: str = typer.Option(None, "--preset", "-p", help="스타일 프리셋"),
    output: str = typer.Option("outputs", "--output", "-o", help="출력 디렉토리")
):
    """스토리로부터 영상 생성"""
    from core.application.story_service import StoryApplicationService
    from core.application.orchestrator import PipelineOrchestrator
    from infrastructure.persistence.database import get_database

    async def run():
        # 입력 확인
        if not title or not content:
            console.print("[red]제목과 내용을 입력해주세요.[/red]")
            return

        console.print(f"[bold green]🎬 영상 생성 시작[/bold green]")
        console.print(f"  제목: {title}")
        console.print(f"  언어: {language}")
        console.print(f"  키워드: {', '.join(keywords) if keywords else '없음'}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("초기화 중...", total=None)

            # DB 초기화
            db = await get_database()

            # 서비스 생성
            story_repo = StoryApplicationService.StoryRepository(db.session)
            task_repo = TaskRepository(db.session)

            # 스토리 생성
            story = await story_repo.save(Story(
                title=title,
                content=content,
                keywords=keywords,
                language=language
            ))

            progress.update(task, description="파이프라인 실행 중...")

            # 파이프라인 실행
            orchestrator = PipelineOrchestrator(story_repo, task_repo)
            result = await orchestrator.generate_video(
                story=story,
                preset_id=preset,
                output_dir=output
            )

            if result.status.value == "completed":
                console.print(f"\n[bold green]✅ 영상 생성 완료![/bold green]")
                console.print(f"  출력: {result.output_paths[0] if result.output_paths else 'N/A'}")
            else:
                console.print(f"\n[bold red]❌ 영상 생성 실패: {result.error_message}[/bold red]")

    asyncio.run(run())


@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-n", help="표시 개수")
):
    """생성된 영상 목록"""
    from infrastructure.persistence.database import get_database
    from infrastructure.persistence.repositories.story_repo import StoryRepository

    async def run():
        db = await get_database()
        repo = StoryRepository(db.session)
        stories = await repo.find_all(limit)

        table = Table(title="📋 생성된 스토리")
        table.add_column("ID", style="cyan")
        table.add_column("제목", style="green")
        table.add_column("언어", style="yellow")
        table.add_column("생성일", style="dim")

        for s in stories:
            table.add_row(
                s.id[:12] + "...",
                s.title[:30],
                s.language.value,
                s.created_at.strftime("%Y-%m-%d %H:%M")
            )

        console.print(table)

    asyncio.run(run())


@app.command()
def presets():
    """스타일 프리셋 목록"""
    from infrastructure.persistence.database import get_database
    from infrastructure.persistence.repositories.preset_repo import PresetRepository

    async def run():
        db = await get_database()
        repo = PresetRepository(db.session)
        preset_list = await repo.find_all()

        table = Table(title="🎨 스타일 프리셋")
        table.add_column("이름", style="cyan")
        table.add_column("설명", style="green")
        table.add_column("기본값", style="yellow")

        for p in preset_list:
            table.add_row(
                p.name,
                p.description[:40] if p.description else "-",
                "⭐" if p.is_default else ""
            )

        console.print(table)

    asyncio.run(run())


@app.command()
def recommend(
    count: int = typer.Option(5, "--count", "-c", help="추천 개수"),
    keywords: List[str] = typer.Option([], "--keyword", "-k", help="키워드")
):
    """AI 스토리 추천"""
    from infrastructure.ai.claude_provider import ClaudeProvider

    async def run():
        try:
            provider = ClaudeProvider()
            recommendations = await provider.recommend_next_stories(
                keywords=keywords,
                count=count
            )

            console.print(f"\n[bold cyan]🎯 추천 스토리 {len(recommendations)}개[/bold cyan]\n")

            for i, rec in enumerate(recommendations, 1):
                console.print(f"[bold]{i}. {rec.get('title', 'Unknown')}[/bold]")
                console.print(f"   {rec.get('description', '')}")
                console.print(f"   [dim]키워드: {', '.join(rec.get('keywords', []))}[/dim]\n")

            await provider.close()

        except Exception as e:
            console.print(f"[red]추천 실패: {e}[/red]")

    asyncio.run(run())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p")
):
    """API 서버 시작"""
    import uvicorn
    console.print(f"[bold green]🚀 API 서버 시작: http://{host}:{port}[/bold green]")
    uvicorn.run("interfaces.api.main:app", host=host, port=port, reload=True)


@app.command()
def init():
    """프로젝트 초기화"""
    console.print("[bold cyan]🔧 프로젝트 초기화...[/bold cyan]")

    # 디렉토리 생성
    dirs = [
        "outputs/videos",
        "outputs/audio",
        "outputs/images",
        "data",
        "models/sd35",
        "models/ip_adapter",
        "models/lora"
    ]

    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"  ✓ {d}/")

    console.print("\n[bold green]✅ 초기화 완료![/bold green]")
    console.print("\n다음 단계:")
    console.print("  1. .env 파일 생성 (API 키 설정)")
    console.print("  2. autonomous create --title \"제목\" --content \"내용\"")


if __name__ == "__main__":
    app()
