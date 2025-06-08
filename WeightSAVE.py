import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
import json

class SkinWeightToolUI:
    def __init__(self):
        self.window = "WeightExportToolUI"
        self.widgets = {}

        # プロジェクトの scenes/_weight フォルダを取得して保存先にする
        scenes_path = cmds.workspace(q=True, rootDirectory=True) + "scenes"
        self.folder_path = os.path.join(scenes_path, "_weight")
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

    def show(self):
        if cmds.window(self.window, exists=True):
            cmds.deleteUI(self.window)

        self.window = cmds.window(self.window, title="ウェイトエクスポートツール", widthHeight=(400, 500))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10)

        cmds.text(label="IMPORT")
        self.widgets["fileList"] = cmds.textScrollList(numberOfRows=8, allowMultiSelection=False, height=150)

        cmds.text(label="インポート方法")
        self.widgets["mode"] = cmds.radioButtonGrp(labelArray3=["頂点番号", "頂点位置", "UV座標値"],
                                                   numberOfRadioButtons=3, select=1)

        cmds.button(label="インポートする", command=self.import_clicked)

        cmds.separator(style="in")
        cmds.text(label="サフィックスをつける")
        self.widgets["suffix"] = cmds.textField()

        cmds.button(label="エクスポートする", command=self.export_clicked)

        cmds.separator(style="in")
        cmds.text(label=f"保存先: {self.folder_path}")

        cmds.button(label="ファイル一覧を更新", command=self.refresh_file_list)

        cmds.showWindow(self.window)

    def get_skin_cluster(self, mesh_name):
        history = cmds.listHistory(mesh_name)
        skin_clusters = cmds.ls(history, type='skinCluster')
        return skin_clusters[0] if skin_clusters else None

    def export_weights(self, mesh, file_path):
        skin_cluster = self.get_skin_cluster(mesh)
        if not skin_cluster:
            cmds.warning(f"{mesh} にスキンクラスタが見つかりません。")
            return

        influences = cmds.skinCluster(skin_cluster, q=True, inf=True)
        weights, positions, uvs = [], [], []

        for i in range(cmds.polyEvaluate(mesh, vertex=True)):
            w = cmds.skinPercent(skin_cluster, f"{mesh}.vtx[{i}]", q=True, v=True)
            weights.append(w)
            positions.append(cmds.pointPosition(f"{mesh}.vtx[{i}]", w=True))
            uv = cmds.polyEditUV(cmds.polyListComponentConversion(f"{mesh}.vtx[{i}]", fv=True, tuv=True)[0], q=True)
            uvs.append(uv if uv else [0.0, 0.0])

        data = {
            "mesh": mesh,
            "influences": influences,
            "weights": weights,
            "positions": positions,
            "uvs": uvs
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def import_weights(self, mesh, file_path, mode):
        if not os.path.exists(file_path):
            cmds.warning(f"ファイルが見つかりません: {file_path}")
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        influences = data["influences"]
        weights = data["weights"]
        positions = data["positions"]
        uvs = data["uvs"]

        skin_cluster = self.get_skin_cluster(mesh)
        if not skin_cluster:
            skin_cluster = cmds.skinCluster(influences, mesh, toSelectedBones=True)[0]

        count = cmds.polyEvaluate(mesh, vertex=True)
        for i in range(count):
            if mode == "index":
                if i >= len(weights): continue
                w = weights[i]
            elif mode == "position":
                p = cmds.pointPosition(f"{mesh}.vtx[{i}]", w=True)
                idx = min(range(len(positions)), key=lambda j: sum([(p[k]-positions[j][k])**2 for k in range(3)]))
                w = weights[idx]
            elif mode == "uv":
                uv = cmds.polyEditUV(cmds.polyListComponentConversion(f"{mesh}.vtx[{i}]", fv=True, tuv=True)[0], q=True)
                idx = min(range(len(uvs)), key=lambda j: sum([(uv[k]-uvs[j][k])**2 for k in range(2)]))
                w = weights[idx]
            else:
                continue

            cmds.skinPercent(skin_cluster, f"{mesh}.vtx[{i}]", transformValue=list(zip(influences, w)))

    def refresh_file_list(self, *_):
        files = [f for f in os.listdir(self.folder_path) if f.endswith(".json")]
        cmds.textScrollList(self.widgets["fileList"], e=True, removeAll=True)
        for f in files:
            cmds.textScrollList(self.widgets["fileList"], e=True, append=f)

    def export_clicked(self, *_):
        suffix = cmds.textField(self.widgets["suffix"], q=True, text=True)
        selection = cmds.ls(sl=True, type="transform")
        if not selection:
            cmds.warning("メッシュを選択してください")
            return

        for mesh in selection:
            filename = f"{mesh}_{suffix}.json" if suffix else f"{mesh}.json"
            path = os.path.join(self.folder_path, filename)
            self.export_weights(mesh, path)

        cmds.inViewMessage(amg="エクスポート完了", pos="topCenter", fade=True)
        self.refresh_file_list()

    def import_clicked(self, *_):
        selected = cmds.textScrollList(self.widgets["fileList"], q=True, selectItem=True)
        if not selected:
            cmds.warning("ファイルを選択してください")
            return

        mode_id = cmds.radioButtonGrp(self.widgets["mode"], q=True, select=True)
        mode_str = {1: "index", 2: "position", 3: "uv"}[mode_id]

        file_path = os.path.join(self.folder_path, selected[0])
        selection = cmds.ls(sl=True, type="transform")
        if not selection:
            cmds.warning("インポート先メッシュを選択してください")
            return

        for mesh in selection:
            self.import_weights(mesh, file_path, mode_str)

        cmds.inViewMessage(amg="インポート完了", pos="topCenter", fade=True)


# 実行
tool = SkinWeightToolUI()
tool.show()
