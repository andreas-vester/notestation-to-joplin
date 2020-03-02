import asyncio
import collections
import distutils.version
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Any

from joplin_api import JoplinApi


class nsx2joplin:
    """nsx2joplin extracts notes from Synlogy Note Station and saves
    them to the Joplinnote app.

    Returns
    -------
    None
    """

    def __init__(self) -> None:
        """Instantiate the nsx2joplin object.

        It will be checked if pandoc is correctly installed.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        def check_pandoc():
            pandoc_input_file = tempfile.NamedTemporaryFile(delete=False)
            pandoc_output_file = tempfile.NamedTemporaryFile(delete=False)

            if not shutil.which("pandoc") and not os.path.isfile("pandoc"):
                print(
                    "Can't find pandoc. Please install pandoc or place it to the "
                    "directory, where the script is."
                )
                exit(1)

            try:
                pandoc_ver = (
                    subprocess.check_output(["pandoc", "-v"], timeout=3)
                    .decode("utf-8")[7:]
                    .split("\n", 1)[0]
                    .strip()
                )
                print("Found pandoc " + pandoc_ver)

                if distutils.version.LooseVersion(
                    pandoc_ver
                ) < distutils.version.LooseVersion("1.16"):
                    pandoc_args = [
                        "pandoc",
                        "-f",
                        "html",
                        "-t",
                        "markdown_strict+pipe_tables-raw_html",
                        "--no-wrap",
                        "-o",
                        pandoc_output_file.name,
                        pandoc_input_file.name,
                    ]
                elif distutils.version.LooseVersion(
                    pandoc_ver
                ) < distutils.version.LooseVersion("1.19"):
                    pandoc_args = [
                        "pandoc",
                        "-f",
                        "html",
                        "-t",
                        "markdown_strict+pipe_tables-raw_html",
                        "--wrap=none",
                        "-o",
                        pandoc_output_file.name,
                        pandoc_input_file.name,
                    ]
                else:
                    pandoc_args = [
                        "pandoc",
                        "-f",
                        "html",
                        "-t",
                        "markdown_strict+pipe_tables-raw_html",
                        "--wrap=none",
                        "--atx-headers",
                        "-o",
                        pandoc_output_file.name,
                        pandoc_input_file.name,
                    ]
            except Exception:
                pandoc_args = [
                    "pandoc",
                    "-f",
                    "html",
                    "-t",
                    "markdown_strict+pipe_tables-raw_html",
                    "--wrap=none",
                    "--atx-headers",
                    "-o",
                    pandoc_output_file.name,
                    pandoc_input_file.name,
                ]

            return pandoc_input_file, pandoc_output_file, pandoc_args

        (
            self._pandoc_input_file,
            self._pandoc_output_file,
            self._pandoc_args,
        ) = check_pandoc()

    def extract_data_from_nsx(
        self,
        nsx_file: str,
        media_folder: str = "attachments",
        save_pickle: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Reads a Synology Note Station .nsx file and extracts its
        content. It will be saved in a dict comprising notebooks and
        notes information.

        Parameters
        ----------
        nsx_file : str
            File name (including path) of the Synology Note Station
            .nsx file
        media_folder : str, optional (default: 'attachments')
            Folder name where all extracted attachments will be saved.
        save_pickle : bool, optional (default: False)
            If True, the extracted data will be saved in a
            nsx_content.pickle file. This might be useful if you want
            to further process the extracted data.

        Returns
        -------
        Dict[str, List[Dict[str, Any]]]
            Python dictionary with keys 'notebooks' and 'notes'.
            It will contain all relevant extracted information
            that will be necessary to use for an import into
            another note taking app.
        """

        def sanitise_path_string(path_str):
            for char in (":", "/", "\\", "|"):
                path_str = path_str.replace(char, "-")
            for char in ("?", "*"):
                path_str = path_str.replace(char, "")
            path_str = path_str.replace("<", "(")
            path_str = path_str.replace(">", ")")
            path_str = path_str.replace('"', "'")

            return path_str[:240]

        work_path = Path.cwd()
        media_folder = sanitise_path_string(media_folder)

        Notebook = collections.namedtuple("Notebook", ["path", "media_path"])

        files_to_convert = Path(work_path).glob("*.nsx")

        if not files_to_convert:
            print("No .nsx files found")
            exit(1)

        nsx_zip = zipfile.ZipFile(nsx_file)
        config_data = json.loads(nsx_zip.read("config.json").decode("utf-8"))
        notebook_id_to_path_index = dict()

        print(f"Extracting notes from {nsx_zip.filename}")

        notebooks = list()
        for notebook_id in config_data["notebook"]:
            notebook_data = json.loads(nsx_zip.read(notebook_id).decode("utf-8"))
            notebook_title = notebook_data["title"] or "Untitled"
            notebook_path = work_path.joinpath(sanitise_path_string(notebook_title))

            print(f"Reading notebook {notebook_title}")

            n = 1
            while notebook_path.is_dir():
                notebook_path = work_path.joinpath(
                    Path(f"{sanitise_path_string(notebook_title)}_{n}")
                )
                n += 1

            notebook_media_path = Path(notebook_path / media_folder)
            notebook_media_path.mkdir(parents=True)

            notebook_id_to_path_index[notebook_id] = Notebook(
                notebook_path, notebook_media_path
            )

            notebooks.append(
                {
                    "id": notebook_id,
                    "title": notebook_data["title"] or "Untitled",
                    "ctime": notebook_data["ctime"],
                    "mtime": notebook_data["ctime"],
                    "path": notebook_path,
                    "media_path": notebook_media_path,
                }
            )

        note_id_to_title_index = {}

        notes = list()
        for idx, note_id in enumerate(config_data["note"], start=1):
            note_data = json.loads(nsx_zip.read(note_id).decode("utf-8"))
            note_title = note_data.get("title", "Untitled")
            note_id_to_title_index[note_id] = note_title
            num_notes = len(config_data["note"])

            try:
                parent_notebook_id = note_data["parent_id"]
                parent_notebook = notebook_id_to_path_index[parent_notebook_id]
            except KeyError:
                continue

            print(f"Reading note {idx}/{num_notes}: {note_title}")

            content = re.sub(
                "< img class=[ ^ >]*syno-notestation-image-object[^>]*"
                "src=[ ^ >]*ref=",
                "<img src=",
                note_data.get("content", ""),
            )

            Path(self._pandoc_input_file.name).write_text(content, "utf-8")
            pandoc = subprocess.Popen(self._pandoc_args)
            pandoc.wait(20)
            content = Path(self._pandoc_output_file.name).read_text("utf-8")

            attachments = None
            if "attachment" in note_data:
                attachments = list()
                for attachment in note_data["attachment"]:
                    name = sanitise_path_string(
                        note_data["attachment"][attachment]["name"]
                    )
                    name = name.replace("ns_attach_image_", "")
                    md5 = None
                    if "md5" in note_data["attachment"][attachment]:
                        md5 = note_data["attachment"][attachment]["md5"]
                    ref = None
                    if "ref" in note_data["attachment"][attachment]:
                        ref = note_data["attachment"][attachment]["ref"]

                    # check if attachment file really exists
                    try:
                        if md5:
                            nsx_zip.read("file_" + md5)
                            attachments.append(
                                {
                                    "id": attachment,
                                    "md5": md5,
                                    "name": name,
                                    "ref": ref,
                                    "type": note_data["attachment"][attachment]["type"],
                                }
                            )

                            Path(parent_notebook.media_path / name).write_bytes(
                                nsx_zip.read("file_" + md5)
                            )
                    except KeyError:
                        continue

            tag = None
            if "tag" in note_data:
                tag = note_data["tag"]

            notes.append(
                {
                    "id": note_id,
                    "parent_nb_id": note_data["parent_id"],
                    "title": note_data.get("title", "Untitled"),
                    "content": content,
                    "attachment": attachments,
                    "tag": tag,
                    "source_url": note_data.get("sourcle_url", ""),
                    "ctime": note_data.get("ctime", ""),
                    "mtime": note_data.get("mtime", ""),
                    "latitude": note_data.get("latitude", ""),
                    "longitude": note_data.get("longitude", ""),
                }
            )

        nsx_content = {"notebooks": notebooks, "notes": notes}

        # save nsx_content as pickle-file
        if save_pickle:
            with open("nsx_content.pickle", "wb") as output_file:
                pickle.dump(nsx_content, output_file)
            print("Saved nsx_content to nsx_content.pickle")

        return nsx_content

    def export_to_joplin(self, token: str, nsx_content: Dict) -> None:
        """Exports notes to Joplin

        Parameters
        ----------
        token : str
            Authorization token. Within the Joplin app, go to
            Tools/Options/Web Clipper to find token.
        nsx_content : Dict
            Python dictionary with keys 'notebooks' and 'notes'.
            It will contain all relevant extracted information
            that will be necessary to use for an import into
            another note taking app.

        Returns
        -------
        None
        """
        joplin = JoplinApi(token=token)

        async def create_folder(notebook_title):
            res = await joplin.create_folder(folder=notebook_title)
            data = res.json()
            parent_id = data["id"]
            assert type(parent_id) is str

            return parent_id

        async def create_resource(attachments, content, attachment_path):
            for index, attachment in enumerate(attachments, start=0):

                attachment_type = attachment["type"]
                name = attachment["name"]

                res = await joplin.create_resource(
                    attachment_path.joinpath(name), **{"title": name}
                )
                resource_id = res.json()["id"]
                attachments[index]["joplin_resource_id"] = resource_id
                assert res.status_code == 200

                if attachment_type == "image":
                    content = re.sub(
                        r"!\[\]\(.*\)", f"![{name}](:/{resource_id})", content, 1,
                    )
                elif attachment_type == "binary":
                    content = f"[{name}](:/{resource_id})\n\n" + content

            return content

        async def create_note(
            joplin_id,
            note_title,
            note_content,
            note_tags,
            user_created_time,
            user_updated_time,
        ):
            body = note_content
            assert type(body) is str
            kwargs = {
                "tags": note_tags,
                "user_created_time": user_created_time,
                "user_updated_time": user_updated_time,
            }
            res = await joplin.create_note(
                title=note_title, body=body, parent_id=joplin_id, **kwargs
            )
            assert res.status_code == 200

        for notebook in nsx_content["notebooks"]:
            joplin_id = asyncio.run(create_folder(notebook["title"]))

            # filter notes that belong to current notebook
            filtered_notes = [
                note
                for note in nsx_content["notes"]
                if note["parent_nb_id"] == notebook["id"]
            ]
            num_filtered_notes = len(filtered_notes)

            for idx, note in enumerate(filtered_notes, start=1):

                print(
                    f"Writing note {idx}/{num_filtered_notes} in {notebook['title']}: "
                    f"{note['title']}"
                )

                # transform list of tags to string
                tag = None
                if note["tag"]:
                    tag = ",".join(note["tag"])

                # Create resource, if necessary
                if note["attachment"]:
                    note["content"] = asyncio.run(
                        create_resource(
                            attachments=note["attachment"],
                            content=note["content"],
                            attachment_path=notebook["media_path"],
                        )
                    )

                asyncio.run(
                    create_note(
                        joplin_id=joplin_id,
                        note_title=note["title"],
                        note_content=note["content"],
                        note_tags=tag,
                        user_created_time=note["ctime"] * 1000,
                        user_updated_time=note["mtime"] * 1000,
                    )
                )

                if idx % 1000 == 0:
                    seconds = 300
                    print(
                        f"Sleep for {seconds} seconds in order to not crash Joplin web "
                        "clipper"
                    )
                    time.sleep(seconds)
                elif idx % 500 == 0:
                    seconds = 120
                    print(
                        f"Sleep for {seconds} seconds in order to not crash Joplin web "
                        "clipper"
                    )
                    time.sleep(seconds)


if __name__ == "__main__":
    # intantiate nsx2joplin object
    nsx = nsx2joplin()

    # step 1: extract notes from Synology Note Station
    # Put your .nsx file here
    p = Path(__file__).resolve().parent
    nsx_file = p.joinpath("notestation-test-books.nsx")

    # possibility to load a previously saved .pickle file
    load_nsx_content = False

    if load_nsx_content:
        pickle_file = "nsx_content.pickle"
        with open(pickle_file, "rb") as input_file:
            nsx_content = pickle.load(input_file)
        print("Loaded nsx_content from nsx_content.pickle")
    else:
        nsx_content = nsx.extract_data_from_nsx(nsx_file=nsx_file, save_pickle=False)

    # step 2: write notes to Joplin notes app
    joplin_token = ""  # noqa
    nsx.export_to_joplin(token=joplin_token, nsx_content=nsx_content)
